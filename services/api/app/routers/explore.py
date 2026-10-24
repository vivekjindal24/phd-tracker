"""Scholar timeline and global search (PRD F11, F12). Every row filtered by the same scope
and redaction rules as its own list — nothing here widens visibility."""

import uuid
from datetime import UTC, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import meetings, scope, seminars
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.enums import MILESTONE_TYPES
from app.models import (
    Conference,
    Faculty,
    Meeting,
    Milestone,
    OrgUnit,
    ProgressReport,
    Publication,
    Scholar,
    Seminar,
    SeminarScholar,
    ThesisSubmission,
    User,
)
from app.modules import module_enabled
from app.rbac import can
from app.workflow import STEP_LABELS

router = APIRouter(tags=["explore"])
GROUP_LIMIT = 8
MILESTONE_LABELS = {k: k.replace("_", " ").capitalize() for k in MILESTONE_TYPES}


def _as_dt(value) -> datetime:
    return value if isinstance(value, datetime) else datetime.combine(value, time(), tzinfo=UTC)


MODULE_OF = {
    "publications": "publications",
    "conferences": "conferences",
    "thesis_submissions": "documents",
}


async def _visible_for(session, principal, entity: str, scholar_id: uuid.UUID) -> bool:
    if not can(principal, entity, "read"):
        return False
    if entity in MODULE_OF and not await module_enabled(session, MODULE_OF[entity]):
        return False
    return bool(
        await session.scalar(
            select(Scholar.id).where(
                Scholar.id == scholar_id, scope.scholar_predicate(principal, entity)
            )
        )
    )


@router.get("/scholars/{scholar_id}/timeline")
async def timeline(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    path = await scope.unit_path(session, scholar.unit_id)
    events: list[dict[str, Any]] = []
    if await _visible_for(session, principal, "meetings", scholar_id):
        for m in await session.scalars(
            select(Meeting).where(Meeting.scholar_id == scholar_id, Meeting.deleted_at.is_(None))
        ):
            full = meetings.sees_full(principal, m, scholar, path)
            events.append(
                {
                    "at": _as_dt(m.meeting_date),
                    "kind": "meeting",
                    "title": m.agenda if full else "Meeting held",
                    "detail": None if full else "Minutes not shared with your role",
                    "link": f"/meetings/{m.id}",
                    "badge": None,
                }
            )
    if await _visible_for(session, principal, "progress_reports", scholar_id):
        for r in await session.scalars(
            select(ProgressReport).where(
                ProgressReport.scholar_id == scholar_id, ProgressReport.deleted_at.is_(None)
            )
        ):
            kind = r.chain_snapshot[r.current_step]["kind"] if r.current_step is not None else None
            events.append(
                {
                    "at": r.approved_at or r.submitted_at or r.created_at,
                    "kind": "report",
                    "title": f"Progress report · {r.period} {r.report_year}",
                    "detail": f"Waiting on {STEP_LABELS[kind]}" if kind else None,
                    "link": f"/items/progress_report/{r.id}",
                    "badge": r.state,
                }
            )
    if await _visible_for(session, principal, "milestones", scholar_id):
        for d in await session.scalars(
            select(Milestone).where(
                Milestone.scholar_id == scholar_id, Milestone.deleted_at.is_(None)
            )
        ):
            events.append(
                {
                    "at": _as_dt(d.resolution_date) if d.resolution_date else d.created_at,
                    "kind": "decision",
                    "title": f"{MILESTONE_LABELS[d.milestone_type]} · {d.approval_body}",
                    "detail": d.resolution_number,
                    "link": f"/scholars/{scholar_id}",
                    "badge": d.status,
                }
            )
    if await _visible_for(session, principal, "publications", scholar_id):
        for p in await session.scalars(
            select(Publication).where(
                Publication.scholar_id == scholar_id, Publication.deleted_at.is_(None)
            )
        ):
            step = p.chain_snapshot[p.current_step]["kind"] if p.current_step is not None else None
            events.append(
                {
                    "at": p.approved_at or p.submitted_at or p.created_at,
                    "kind": "publication",
                    "title": p.title,
                    "detail": f"Waiting on {STEP_LABELS[step]}" if step else p.venue,
                    "link": f"/items/publication/{p.id}",
                    "badge": p.state,
                }
            )
    if await _visible_for(session, principal, "conferences", scholar_id):
        for c in await session.scalars(
            select(Conference).where(
                Conference.scholar_id == scholar_id, Conference.deleted_at.is_(None)
            )
        ):
            events.append(
                {
                    "at": _as_dt(c.event_date),
                    "kind": "conference",
                    "title": c.event_name,
                    "detail": c.title or c.event_type.replace("_", " ").capitalize(),
                    "link": "/conferences",
                    "badge": None,
                }
            )
    if await _visible_for(session, principal, "thesis_submissions", scholar_id):
        for t in await session.scalars(
            select(ThesisSubmission).where(
                ThesisSubmission.scholar_id == scholar_id, ThesisSubmission.deleted_at.is_(None)
            )
        ):
            step = t.chain_snapshot[t.current_step]["kind"] if t.current_step is not None else None
            events.append(
                {
                    "at": t.approved_at or t.submitted_at or t.created_at,
                    "kind": "thesis",
                    "title": f"Thesis · {t.title}",
                    "detail": f"Waiting on {STEP_LABELS[step]}" if step else None,
                    "link": f"/items/thesis_submission/{t.id}",
                    "badge": t.state,
                }
            )
    open_ = await seminars.open_to_faculty(session)
    for s in await session.scalars(
        select(Seminar)
        .join(SeminarScholar, SeminarScholar.seminar_id == Seminar.id)
        .where(
            SeminarScholar.scholar_id == scholar_id,
            SeminarScholar.deleted_at.is_(None),
            Seminar.deleted_at.is_(None),
            seminars.visible(principal, open_),
        )
    ):
        events.append(
            {
                "at": s.starts_at,
                "kind": "seminar",
                "title": s.title,
                "detail": f"Report due {s.report_due:%d %b %Y}",
                "link": f"/seminars/{s.id}",
                "badge": "cancelled" if s.status == "cancelled" else None,
            }
        )
    return sorted(events, key=lambda e: e["at"], reverse=True)


@router.get("/search")
async def search(
    q: str = Query(min_length=2, max_length=100),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict[str, Any]]]:
    like = f"%{q.strip()}%"
    ScholarUser = aliased(User)
    out: dict[str, list[dict[str, Any]]] = {}

    rows = await session.execute(
        select(Scholar.id, User.full_name, Scholar.roll_number)
        .join(User, User.id == Scholar.user_id)
        .where(
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "scholars"),
            or_(
                User.full_name.ilike(like),
                Scholar.roll_number.ilike(like),
                Scholar.research_title.ilike(like),
            ),
        )
        .order_by(User.full_name)
        .limit(GROUP_LIMIT)
    )
    out["scholars"] = [{"title": n, "detail": r, "link": f"/scholars/{i}"} for i, n, r in rows]

    rows = await session.execute(
        select(User.full_name, OrgUnit.name)
        .join(Faculty, Faculty.user_id == User.id)
        .join(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .where(Faculty.deleted_at.is_(None), User.full_name.ilike(like))
        .order_by(User.full_name)
        .limit(GROUP_LIMIT)
    )
    out["faculty"] = [{"title": n, "detail": u, "link": "/faculty"} for n, u in rows]

    out["reports"] = []
    if can(principal, "progress_reports", "read"):
        rows = await session.execute(
            select(ProgressReport, ScholarUser.full_name)
            .join(Scholar, Scholar.id == ProgressReport.scholar_id)
            .join(ScholarUser, ScholarUser.id == Scholar.user_id)
            .where(
                ProgressReport.deleted_at.is_(None),
                scope.scholar_predicate(principal, "progress_reports"),
                ProgressReport.summary.ilike(like),
            )
            .limit(GROUP_LIMIT)
        )
        out["reports"] = [
            {
                "title": f"{r.period} {r.report_year}",
                "detail": n,
                "link": f"/items/progress_report/{r.id}",
            }
            for r, n in rows
        ]

    out["meetings"] = []
    if can(principal, "meetings", "read"):
        rows = await session.execute(
            select(Meeting, Scholar, OrgUnit.path, ScholarUser.full_name)
            .join(Scholar, Scholar.id == Meeting.scholar_id)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .join(ScholarUser, ScholarUser.id == Scholar.user_id)
            .where(
                Meeting.deleted_at.is_(None),
                scope.scholar_predicate(principal, "meetings"),
                Meeting.agenda.ilike(like),
            )
            .order_by(Meeting.meeting_date.desc())
            .limit(GROUP_LIMIT * 3)
        )
        # Agenda matches only for viewers who may read the meeting in full (redaction).
        out["meetings"] = [
            {
                "title": m.agenda,
                "detail": f"{n} · {m.meeting_date:%d %b %Y}",
                "link": f"/meetings/{m.id}",
            }
            for m, sc, path, n in rows
            if meetings.sees_full(principal, m, sc, path)
        ][:GROUP_LIMIT]

    out["decisions"] = []
    if can(principal, "milestones", "read"):
        rows = await session.execute(
            select(Milestone, ScholarUser.full_name, Scholar.id)
            .join(Scholar, Scholar.id == Milestone.scholar_id)
            .join(ScholarUser, ScholarUser.id == Scholar.user_id)
            .where(
                Milestone.deleted_at.is_(None),
                scope.scholar_predicate(principal, "milestones"),
                Milestone.resolution_number.ilike(like),
            )
            .limit(GROUP_LIMIT)
        )
        out["decisions"] = [
            {
                "title": d.resolution_number,
                "detail": f"{n} · {MILESTONE_LABELS[d.milestone_type]}",
                "link": f"/scholars/{sid}",
            }
            for d, n, sid in rows
        ]

    out["publications"] = []
    if can(principal, "publications", "read") and await module_enabled(session, "publications"):
        rows = await session.execute(
            select(Publication, ScholarUser.full_name)
            .join(Scholar, Scholar.id == Publication.scholar_id)
            .join(ScholarUser, ScholarUser.id == Scholar.user_id)
            .where(
                Publication.deleted_at.is_(None),
                scope.scholar_predicate(principal, "publications"),
                or_(Publication.title.ilike(like), Publication.venue.ilike(like)),
            )
            .order_by(Publication.pub_year.desc())
            .limit(GROUP_LIMIT)
        )
        out["publications"] = [
            {
                "title": p.title,
                "detail": f"{n} · {p.venue} · {p.pub_year}",
                "link": f"/items/publication/{p.id}",
            }
            for p, n in rows
        ]

    open_ = await seminars.open_to_faculty(session)
    rows = await session.execute(
        select(Seminar.id, Seminar.title, Seminar.starts_at)
        .where(
            Seminar.deleted_at.is_(None),
            seminars.visible(principal, open_),
            Seminar.title.ilike(like),
        )
        .order_by(Seminar.starts_at.desc())
        .limit(GROUP_LIMIT)
    )
    out["seminars"] = [
        {"title": t, "detail": f"{s:%d %b %Y}", "link": f"/seminars/{i}"} for i, t, s in rows
    ]
    return out
