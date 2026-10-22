"""Home dashboards (PRD F10): one section per role the caller holds, all scoped by scope.py.
Report deadlines come from progress seminars (PRD F8/F15)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, scope, seminars
from app.auth.principal import Principal
from app.enums import STAGES
from app.models import (
    ApprovalActionRow,
    Faculty,
    Meeting,
    Milestone,
    OrgUnit,
    ProgressReport,
    RoleAssignment,
    Scholar,
    Seminar,
    SeminarScholar,
    Todo,
    User,
)
from app.workflow import STEP_LABELS

DUE_SOON_DAYS = 14  # PRD F8
STUCK_DAYS = 14  # PRD F10
SUBMITTED = ("in_review", "approved")
LIST_LIMIT = 20


def due_status(report_due: date, report_state: str | None, today: date) -> str:
    if report_state in SUBMITTED:
        return "submitted"
    if today > report_due:
        return "overdue"
    if (report_due - today).days <= DUE_SOON_DAYS:
        return "due_soon"
    return "upcoming"


def _deadlines_query(scholar_filter):
    """One row per (scholar, live seminar): the seminar's report deadline and the state of
    the scholar's report for that seminar's period."""
    report = and_(
        ProgressReport.scholar_id == Scholar.id,
        ProgressReport.report_year == Seminar.report_year,
        ProgressReport.period == Seminar.period,
        ProgressReport.deleted_at.is_(None),
    )
    return (
        select(Seminar, Scholar, User.full_name, ProgressReport.state)
        .join(SeminarScholar, SeminarScholar.seminar_id == Seminar.id)
        .join(Scholar, Scholar.id == SeminarScholar.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .outerjoin(ProgressReport, report)
        .where(
            Seminar.deleted_at.is_(None),
            Seminar.status == "scheduled",
            SeminarScholar.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scholar_filter,
        )
    )


async def _overdue(session: AsyncSession, scholar_filter) -> list[dict[str, Any]]:
    today = datetime.now(UTC).date()
    rows = await session.execute(
        _deadlines_query(scholar_filter)
        .where(Seminar.report_due < today)
        .order_by(Seminar.report_due)
    )
    out = []
    for seminar, scholar, name, state in rows:
        if state not in SUBMITTED:
            out.append(
                {
                    "scholar": {"id": scholar.id, "name": name},
                    "seminar": {"id": seminar.id, "name": seminar.title},
                    "report_due": seminar.report_due,
                }
            )
    return out[:LIST_LIMIT]


async def _scholar_section(session: AsyncSession, principal: Principal) -> dict[str, Any]:
    sid = principal.scholar_id
    scholar = await session.get(Scholar, sid)
    assert scholar is not None
    today = datetime.now(UTC).date()
    sup = None
    if scholar.supervisor_id:
        sup = await session.scalar(
            select(User.full_name)
            .join(Faculty, Faculty.user_id == User.id)
            .where(Faculty.id == scholar.supervisor_id)
        )
    upcoming = (
        await session.execute(
            _deadlines_query(Scholar.id == sid)
            .where(Seminar.starts_at >= datetime.now(UTC) - timedelta(days=1))
            .order_by(Seminar.starts_at)
            .limit(1)
        )
    ).first()
    next_seminar = None
    if upcoming:
        seminar, _, _, state = upcoming
        next_seminar = {
            "id": seminar.id,
            "title": seminar.title,
            "starts_at": seminar.starts_at,
            "venue": seminar.venue,
            "report_due": seminar.report_due,
            "report_period": f"{seminar.period} {seminar.report_year}",
            "due_status": due_status(seminar.report_due, state, today),
        }
    in_progress = []
    for r in await session.scalars(
        select(ProgressReport).where(
            ProgressReport.scholar_id == sid,
            ProgressReport.deleted_at.is_(None),
            ProgressReport.state.in_(("draft", "in_review", "sent_back")),
        )
    ):
        kind = r.chain_snapshot[r.current_step]["kind"] if r.current_step is not None else None
        in_progress.append(
            {
                "item_type": "progress_report",
                "id": r.id,
                "title": f"{r.period} {r.report_year}",
                "state": r.state,
                "waiting_on": STEP_LABELS[kind] if kind else None,
            }
        )
    meetings_q = select(func.max(Meeting.meeting_date), func.max(Meeting.next_meeting_date)).where(
        Meeting.scholar_id == sid, Meeting.deleted_at.is_(None)
    )
    last_meeting, next_meeting = (await session.execute(meetings_q)).one()
    decision = await session.scalar(
        select(Milestone)
        .where(Milestone.scholar_id == sid, Milestone.deleted_at.is_(None))
        .order_by(Milestone.resolution_date.desc().nulls_last(), Milestone.created_at.desc())
        .limit(1)
    )
    open_todos = await session.scalar(
        select(func.count())
        .select_from(Todo)
        .where(Todo.scholar_id == sid, Todo.status == "open", Todo.deleted_at.is_(None))
    )
    return {
        "stage": scholar.stage,
        "supervisor": sup,
        "next_seminar": next_seminar,
        "in_progress": in_progress,
        "open_todos": open_todos or 0,
        "last_meeting": last_meeting,
        "next_meeting": next_meeting if next_meeting and next_meeting >= today else None,
        "latest_decision": (
            {
                "milestone_type": decision.milestone_type,
                "status": decision.status,
                "resolution_number": decision.resolution_number,
                "resolution_date": decision.resolution_date,
            }
            if decision
            else None
        ),
    }


async def _supervisor_section(session: AsyncSession, principal: Principal) -> dict[str, Any]:
    fid = principal.faculty_id
    faculty = await session.get(Faculty, fid)
    mine = Scholar.supervisor_id == fid
    rows = await session.execute(
        select(Scholar.id, User.full_name, Scholar.stage)
        .join(User, User.id == Scholar.user_id)
        .where(mine, Scholar.deleted_at.is_(None))
        .order_by(User.full_name)
    )
    scholars = [{"id": i, "name": n, "stage": s} for i, n, s in rows]
    return {
        "load": len(scholars),
        "max_scholars": faculty.max_scholars if faculty else 0,
        "scholars": scholars,
        "overdue_reports": await _overdue(session, mine),
    }


async def _unit_section(
    session: AsyncSession, unit_id: uuid.UUID, path: str, roles: list[str]
) -> dict[str, Any]:
    units = scope.subtree_unit_ids((path,))
    in_unit = Scholar.unit_id.in_(units)
    stage_rows = await session.execute(
        select(Scholar.stage, func.count())
        .where(in_unit, Scholar.deleted_at.is_(None))
        .group_by(Scholar.stage)
    )
    by_stage = dict.fromkeys(STAGES, 0) | dict(stage_rows.all())
    loads = await session.execute(
        select(
            User.full_name,
            Faculty.max_scholars,
            select(func.count())
            .select_from(Scholar)
            .where(Scholar.supervisor_id == Faculty.id, Scholar.deleted_at.is_(None))
            .correlate(Faculty)
            .scalar_subquery(),
        )
        .join(User, User.id == Faculty.user_id)
        .where(Faculty.unit_id.in_(units), Faculty.deleted_at.is_(None), Faculty.can_supervise)
        .order_by(User.full_name)
    )
    now = datetime.now(UTC)
    stuck = []
    for item_type, kind in items.REGISTRY.items():
        q = (
            select(kind.model, User.full_name, func.max(ApprovalActionRow.at))
            .join(Scholar, Scholar.id == kind.model.scholar_id)
            .join(User, User.id == Scholar.user_id)
            .join(
                ApprovalActionRow,
                and_(
                    ApprovalActionRow.item_type == item_type,
                    ApprovalActionRow.item_id == kind.model.id,
                ),
            )
            .where(kind.model.state == "in_review", kind.model.deleted_at.is_(None), in_unit)
            .group_by(kind.model.id, User.full_name)
        )
        for item, name, since in await session.execute(q):
            days = (now - since).days
            if days > STUCK_DAYS:
                step = item.chain_snapshot[item.current_step]["kind"]
                stuck.append(
                    {
                        "item_type": item_type,
                        "id": item.id,
                        "title": kind.title(item),
                        "scholar": name,
                        "step": STEP_LABELS[step],
                        "days": days,
                    }
                )
    children = []
    child_rows = await session.execute(
        select(OrgUnit.id, OrgUnit.name, OrgUnit.path)
        .where(OrgUnit.parent_id == unit_id, OrgUnit.deleted_at.is_(None))
        .order_by(OrgUnit.name)
    )
    for cid, cname, cpath in child_rows:
        cunits = scope.subtree_unit_ids((cpath,))
        count = await session.scalar(
            select(func.count())
            .select_from(Scholar)
            .where(Scholar.unit_id.in_(cunits), Scholar.deleted_at.is_(None))
        )
        overdue = await _overdue(session, Scholar.unit_id.in_(cunits))
        children.append({"id": cid, "name": cname, "scholars": count or 0, "overdue": len(overdue)})
    section: dict[str, Any] = {
        "unit_id": unit_id,
        "roles": roles,
        "unit_name": await session.scalar(select(OrgUnit.name).where(OrgUnit.id == unit_id)),
        "scholars_by_stage": by_stage,
        "total_scholars": sum(by_stage.values()),
        "overdue_reports": await _overdue(session, in_unit),
        "stuck_items": sorted(stuck, key=lambda s: -s["days"])[:LIST_LIMIT],
        "supervisor_load": [{"name": n, "load": load, "max": m} for n, m, load in loads],
        "children": children,
    }
    if "admin" in roles:
        section["without_supervisor"] = [
            {"id": i, "name": n}
            for i, n in await session.execute(
                select(Scholar.id, User.full_name)
                .join(User, User.id == Scholar.user_id)
                .where(in_unit, Scholar.deleted_at.is_(None), Scholar.supervisor_id.is_(None))
                .order_by(User.full_name)
                .limit(LIST_LIMIT)
            )
        ]
        headed = select(RoleAssignment.unit_id).where(
            RoleAssignment.role == "unit_head", RoleAssignment.deleted_at.is_(None)
        )
        section["units_without_head"] = [
            {"id": i, "name": n}
            for i, n in await session.execute(
                select(OrgUnit.id, OrgUnit.name)
                .where(
                    OrgUnit.id.in_(units), OrgUnit.deleted_at.is_(None), OrgUnit.id.not_in(headed)
                )
                .order_by(OrgUnit.name)
                .limit(LIST_LIMIT)
            )
        ]
    return section


async def build(session: AsyncSession, principal: Principal) -> dict[str, Any]:
    queue = await items.queue(session, principal)
    out: dict[str, Any] = {
        "queue_count": len(queue),
        "queue_oldest_days": max((q["days_waiting"] for q in queue), default=None),
        "queue": queue[:5],
        "upcoming_seminars": [],
    }
    open_ = await seminars.open_to_faculty(session)
    rows = await session.execute(
        select(Seminar.id, Seminar.title, Seminar.starts_at, Seminar.report_due, OrgUnit.name)
        .join(OrgUnit, OrgUnit.id == Seminar.unit_id)
        .where(
            Seminar.deleted_at.is_(None),
            Seminar.status == "scheduled",
            Seminar.starts_at >= datetime.now(UTC),
            seminars.visible(principal, open_),
        )
        .order_by(Seminar.starts_at)
        .limit(5)
    )
    out["upcoming_seminars"] = [
        {"id": i, "title": t, "starts_at": s, "report_due": d, "unit": u} for i, t, s, d, u in rows
    ]
    if principal.scholar_id:
        out["scholar"] = await _scholar_section(session, principal)
    if principal.faculty_id and principal.can_supervise:
        out["supervisor"] = await _supervisor_section(session, principal)
    by_unit: dict[uuid.UUID, tuple[str, list[str]]] = {}
    for r in principal.unit_roles:  # head + admin of one unit -> one section
        by_unit.setdefault(r.unit_id, (r.unit_path, []))[1].append(r.role)
    out["units"] = [
        await _unit_section(session, uid, path, sorted(roles))
        for uid, (path, roles) in by_unit.items()
    ]
    return out
