"""The daily job (ARCHITECTURE.md §10): one call a day from the scheduler, authenticated by the
X-Cron-Secret header, idempotent per day through job_runs. Off when CRON_SECRET is unset."""

import hmac
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Header
from sqlalchemy import cast, func, literal, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, reviews, workflow
from app.config import settings
from app.dashboard import DUE_SOON_DAYS, SUBMITTED, deadlines_query
from app.db import get_session
from app.errors import ApiError
from app.grants import pi_and_office_user_ids
from app.models import (
    ApprovalActionRow,
    EthicsClearance,
    Faculty,
    Fellowship,
    JobRun,
    Meeting,
    OrgUnit,
    Project,
    RoleAssignment,
    Scholar,
    Seminar,
)
from app.models.base import Ltree
from app.modules import module_enabled
from app.notify import notify

router = APIRouter(prefix="/internal/cron", tags=["internal"])
FELLOWSHIP_NOTICE_DAYS = 60  # PRD F5: "fellowship ending in 60 days"
PROJECT_NOTICE_DAYS = 60  # PRD M8: "a project ends within 60 days"


async def _fellowships_ending(session: AsyncSession, today: date) -> int:
    # ponytail: exact-day match, so a day the scheduler misses sends no reminder for
    # fellowships ending that day; track reminded rows if the scheduler proves unreliable.
    if not await module_enabled(session, "fellowships"):
        return 0
    ends = today + timedelta(days=FELLOWSHIP_NOTICE_DAYS)
    rows = await session.execute(
        select(Scholar.user_id, Faculty.user_id)
        .join(Fellowship, Fellowship.scholar_id == Scholar.id)
        .outerjoin(Faculty, Faculty.id == Scholar.supervisor_id)
        .where(
            Fellowship.deleted_at.is_(None),
            Fellowship.status == "active",
            Fellowship.end_date == ends,
            Scholar.deleted_at.is_(None),
            Scholar.left_on.is_(None),
        )
    )
    count = 0
    for scholar_user, supervisor_user in rows:
        notify(
            session,
            [u for u in (scholar_user, supervisor_user) if u],
            "fellowship_ending",
            f"Fellowship ends on {ends:%d %b %Y}",
            f"The fellowship ends in {FELLOWSHIP_NOTICE_DAYS} days. Speak to the research "
            "office about an extension or the next step.",
            "/fellowships",
        )
        count += 1
    return count


ETHICS_NOTICE_DAYS = 60  # PRD F9c


async def _ethics_expiring(session: AsyncSession, today: date) -> int:
    # ponytail: exact-day match, as for fellowships.
    ends = today + timedelta(days=ETHICS_NOTICE_DAYS)
    rows = await session.execute(
        select(Scholar.id, Scholar.user_id, Faculty.user_id)
        .join(EthicsClearance, EthicsClearance.scholar_id == Scholar.id)
        .outerjoin(Faculty, Faculty.id == Scholar.supervisor_id)
        .where(
            EthicsClearance.deleted_at.is_(None),
            EthicsClearance.valid_until == ends,
            Scholar.deleted_at.is_(None),
            Scholar.left_on.is_(None),
        )
    )
    count = 0
    for scholar_id, scholar_user, supervisor_user in rows:
        notify(
            session,
            [u for u in (scholar_user, supervisor_user) if u],
            "system",
            f"Ethics clearance ends on {ends:%d %b %Y}",
            f"The ethics clearance lapses in {ETHICS_NOTICE_DAYS} days. Apply to the ethics "
            "committee for renewal if the work is still going on.",
            f"/scholars/{scholar_id}",
        )
        count += 1
    return count


async def _projects_ending(session: AsyncSession, today: date) -> int:
    # ponytail: exact-day match, as for fellowships.
    if not await module_enabled(session, "projects"):
        return 0
    ends = today + timedelta(days=PROJECT_NOTICE_DAYS)
    projects = await session.scalars(
        select(Project).where(
            Project.deleted_at.is_(None), Project.status == "ongoing", Project.end_date == ends
        )
    )
    count = 0
    for project in projects.all():
        notify(
            session,
            await pi_and_office_user_ids(session, project),
            "grant_alert",
            f"Project ends on {ends:%d %b %Y}: {project.title}",
            f"The project ends in {PROJECT_NOTICE_DAYS} days. Plan the final utilisation "
            "certificate and any extension request with the agency.",
            f"/projects/{project.id}",
        )
        count += 1
    return count


async def _apr_reminders(session: AsyncSession, today: date) -> tuple[int, int]:
    """PRD F8: "due soon" 14 days before the seminar's report due date (to the scholar) and
    "overdue" the day after it (scholar and supervisor), while the report is unsubmitted."""
    soon_day = today + timedelta(days=DUE_SOON_DAYS)
    late_day = today - timedelta(days=1)
    rows = await session.execute(deadlines_query(Seminar.report_due.in_((soon_day, late_day))))
    soon = late = 0
    for seminar, scholar, _, state in rows:
        if state in SUBMITTED:
            continue
        period = f"{seminar.period} {seminar.report_year}"
        if seminar.report_due == soon_day:
            notify(
                session,
                [scholar.user_id],
                "apr_due",
                f"Progress report due {seminar.report_due:%d %b %Y}",
                f"Your {period} progress report is due in {DUE_SOON_DAYS} days, ahead of "
                f"{seminar.title}.",
                "/reports",
            )
            soon += 1
        else:
            supervisor = await session.scalar(
                select(Faculty.user_id).where(Faculty.id == scholar.supervisor_id)
            )
            notify(
                session,
                [u for u in (scholar.user_id, supervisor) if u],
                "apr_due",
                "Progress report overdue",
                f"The {period} progress report was due on {seminar.report_due:%d %b %Y} and "
                "has not been submitted.",
                "/reports",
            )
            late += 1
    return soon, late


async def _meetings_tomorrow(session: AsyncSession, today: date) -> int:
    """PRD F5 "meeting tomorrow": the next meeting date on the latest meeting logged for each
    scholar and supervisor pair (a newer meeting replaces an older plan)."""
    latest = (
        select(Meeting.scholar_id, Meeting.supervisor_id, Meeting.next_meeting_date)
        .where(Meeting.deleted_at.is_(None))
        .ext(distinct_on(Meeting.scholar_id, Meeting.supervisor_id))
        .order_by(
            Meeting.scholar_id,
            Meeting.supervisor_id,
            Meeting.meeting_date.desc(),
            Meeting.created_at.desc(),
        )
        .subquery()
    )
    rows = await session.execute(
        select(Scholar.user_id, Faculty.user_id)
        .select_from(latest)
        .join(Scholar, Scholar.id == latest.c.scholar_id)
        .join(Faculty, Faculty.id == latest.c.supervisor_id)
        .where(
            latest.c.next_meeting_date == today + timedelta(days=1),
            Scholar.deleted_at.is_(None),
            Scholar.left_on.is_(None),
        )
    )
    count = 0
    for scholar_user, faculty_user in rows:
        notify(
            session,
            [scholar_user, faculty_user],
            "meeting_tomorrow",
            "Meeting tomorrow",
            "The next supervision meeting planned at your last meeting is tomorrow.",
            "/meetings",
        )
        count += 1
    return count


async def _waiting_approvals(session: AsyncSession, today: date) -> tuple[int, int]:
    """PRD F3: an item nobody has moved for REMIND_AFTER_DAYS is brought back to the people of
    its step (at the supervisor step also the department's admins, who can chase it); at
    ESCALATE_AFTER_DAYS a supervisor-step item goes to the heads, who may now act on it."""
    # ponytail: exact-day match like the other reminders here, and every in-review item is
    # read; track reminded rows / push the day test into SQL if either starts to matter.
    reminded = escalated = 0
    nobody = uuid.UUID(int=0)
    for item_type, kind in (await items.enabled_kinds(session)).items():
        rows = await session.execute(
            select(kind.model, Scholar, OrgUnit.path)
            .join(Scholar, Scholar.id == kind.model.scholar_id)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .where(kind.model.state == "in_review", kind.model.deleted_at.is_(None))
        )
        for item, scholar, path in rows:
            ctx = workflow.ItemContext(item_type, item, scholar, path)
            step = workflow.current_kind(ctx)
            since = await session.scalar(
                select(func.max(ApprovalActionRow.at)).where(
                    ApprovalActionRow.item_type == item_type,
                    ApprovalActionRow.item_id == item.id,
                )
            )
            if step is None or since is None:
                continue
            days = (today - since.astimezone(UTC).date()).days
            label = f"{ctx.label} · {kind.title(item)}"
            if days == workflow.REMIND_AFTER_DAYS:
                ids = await workflow.step_actor_ids(session, ctx, step, nobody)
                body = f"Waiting {days} days at the {workflow.STEP_LABELS[step]} step."
                if step == "supervisor":
                    ids += await _unit_role_holders(session, path, "admin")
                    body += (
                        " A supervisor who is away can name a stand-in under My account; after "
                        f"{workflow.ESCALATE_AFTER_DAYS} days the head of department may act."
                    )
                notify(session, ids, "approval_waiting", f"Still waiting: {label}", body, ctx.link)
                reminded += 1
            elif days == workflow.ESCALATE_AFTER_DAYS and step == "supervisor":
                notify(
                    session,
                    await _unit_role_holders(session, path, "unit_head"),
                    "approval_waiting",
                    f"Waiting {days} days: {label}",
                    "The supervisor has not acted. As head you can now approve it or send it "
                    "back in their place.",
                    ctx.link,
                )
                escalated += 1
    return reminded, escalated


async def _unit_role_holders(session: AsyncSession, unit_path: str, role: str) -> list[uuid.UUID]:
    """Users holding `role` on the unit or any unit above it."""
    rows = await session.scalars(
        select(RoleAssignment.user_id)
        .join(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
        .where(
            RoleAssignment.deleted_at.is_(None),
            RoleAssignment.role == role,
            OrgUnit.path.op("@>")(cast(literal(unit_path), Ltree)),
        )
    )
    return list(rows)


@router.post("/daily")
async def daily(
    x_cron_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    if settings.cron_secret is None:
        raise ApiError(404, "not_configured", "The daily job is not configured on this server.")
    if x_cron_secret is None or not hmac.compare_digest(
        x_cron_secret.encode(), settings.cron_secret.encode()
    ):
        raise ApiError(401, "unauthorized", "Wrong or missing cron secret.")
    today = datetime.now(UTC).date()
    claimed = await session.scalar(
        insert(JobRun)
        .values(job_name="daily", run_date=today)
        .on_conflict_do_nothing(constraint="uq_job_runs")
        .returning(JobRun.id)
    )
    if claimed is None:
        return {"ran": False, "reason": "already ran today"}
    fellowships = await _fellowships_ending(session, today)
    projects = await _projects_ending(session, today)
    ethics_reminders = await _ethics_expiring(session, today)
    apr_soon, apr_late = await _apr_reminders(session, today)
    meetings = await _meetings_tomorrow(session, today)
    approvals_reminded, approvals_escalated = await _waiting_approvals(session, today)
    review_counts = await reviews.daily(session, today)
    await session.commit()
    return {
        "ran": True,
        "fellowship_reminders": fellowships,
        "project_reminders": projects,
        "ethics_reminders": ethics_reminders,
        "apr_due_soon": apr_soon,
        "apr_overdue": apr_late,
        "meeting_reminders": meetings,
        "approval_reminders": approvals_reminded,
        "approval_escalations": approvals_escalated,
        **review_counts,
    }
