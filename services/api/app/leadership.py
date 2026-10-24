"""The leadership view (PRD Phase 4): scholars at risk, time to completion and drop-outs per
unit, supervisor load. Computed for one unit's subtree; who may ask is decided by the caller
(routers/leadership.py) through the same covers() rules as every other head/admin view."""

import statistics
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import dashboard, directory, duration, scope
from app.models import Faculty, Meeting, Milestone, OrgUnit, Scholar, User

QUIET_DAYS = 120  # no supervision meeting logged for four months
DAYS_PER_YEAR = 365.25
RISK_LIMIT = 50


def _in(path: str, unit_path: str) -> bool:
    return unit_path == path or unit_path.startswith(path + ".")


async def _completion_years(session: AsyncSession, units) -> dict[uuid.UUID, float]:
    """Admission → degree awarded (the register's approved decision), per completed scholar."""
    rows = await session.execute(
        select(Scholar.id, Scholar.admission_date, func.min(Milestone.resolution_date))
        .join(Milestone, Milestone.scholar_id == Scholar.id)
        .where(
            Scholar.unit_id.in_(units),
            Scholar.deleted_at.is_(None),
            Scholar.admission_date.is_not(None),
            Milestone.deleted_at.is_(None),
            Milestone.milestone_type == "degree_awarded",
            Milestone.status == "Approved",
            Milestone.resolution_date.is_not(None),
        )
        .group_by(Scholar.id, Scholar.admission_date)
    )
    return {sid: (awarded - admitted).days / DAYS_PER_YEAR for sid, admitted, awarded in rows}


def _unit_row(unit: dict, scholars: list, years: dict, faculty: list) -> dict[str, Any]:
    current = [s for s in scholars if directory.counts_toward_cap(s)]
    completed = [s for s in scholars if s.stage == directory.COMPLETED_STAGE]
    left = [s for s in scholars if s.left_on is not None]
    known = [years[s.id] for s in completed if s.id in years]
    started = len(current) + len(completed) + len(left)
    loads = [load for _, load, _ in faculty]
    return {
        "unit": unit,
        "current": len(current),
        "completed": len(completed),
        "median_years_to_complete": round(statistics.median(known), 1) if known else None,
        "left": len(left),
        "withdrawn": sum(s.left_reason == "withdrawn" for s in left),
        "cancelled": sum(s.left_reason == "cancelled" for s in left),
        "dropout_rate": round(len(left) / started, 3) if started else None,
        "supervisors": len(faculty),
        "supervisors_at_cap": sum(load >= cap for _, load, cap in faculty),
        "average_load": round(statistics.fmean(loads), 1) if loads else None,
    }


async def build(session: AsyncSession, unit: OrgUnit) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    units = scope.subtree_unit_ids((unit.path,))
    scholar_rows = (
        await session.execute(
            select(Scholar, OrgUnit.path, User.full_name)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .join(User, User.id == Scholar.user_id)
            .where(Scholar.unit_id.in_(units), Scholar.deleted_at.is_(None))
        )
    ).all()
    faculty_rows = (
        await session.execute(
            select(Faculty.id, OrgUnit.path, directory.load_of_faculty(), Faculty.max_scholars)
            .join(OrgUnit, OrgUnit.id == Faculty.unit_id)
            .where(Faculty.unit_id.in_(units), Faculty.deleted_at.is_(None), Faculty.can_supervise)
        )
    ).all()
    years = await _completion_years(session, units)
    children = (
        await session.execute(
            select(OrgUnit.id, OrgUnit.name, OrgUnit.path)
            .where(OrgUnit.parent_id == unit.id, OrgUnit.deleted_at.is_(None))
            .order_by(OrgUnit.name)
        )
    ).all()

    def row_for(uid: uuid.UUID, name: str, path: str) -> dict[str, Any]:
        return _unit_row(
            {"id": uid, "name": name},
            [s for s, p, _ in scholar_rows if _in(path, p)],
            years,
            [(f, load, cap) for f, p, load, cap in faculty_rows if _in(path, p)],
        )

    return {
        "unit": {"id": unit.id, "name": unit.name},
        "total": row_for(unit.id, unit.name, unit.path),
        "by_unit": [row_for(i, n, p) for i, n, p in children],
        "at_risk": await _at_risk(session, scholar_rows, today),
        "as_of": today,
    }


async def _at_risk(session: AsyncSession, scholar_rows, today: date) -> list[dict[str, Any]]:
    current = [(s, name) for s, _, name in scholar_rows if directory.counts_toward_cap(s)]
    if not current:
        return []
    ids = [s.id for s, _ in current]
    reasons: dict[uuid.UUID, list[str]] = defaultdict(list)
    for row in await dashboard.overdue_reports(session, Scholar.id.in_(ids)):
        reasons[row["scholar"]["id"]].append(
            f"Progress report overdue since {row['report_due']:%d %b}"
        )
    assessed = await duration.assess_many(session, [s for s, _ in current], today)
    for sid, a in assessed.items():
        reasons[sid].extend(a["warnings"])
    last_meeting = dict(
        (
            await session.execute(
                select(Meeting.scholar_id, func.max(Meeting.meeting_date))
                .where(Meeting.scholar_id.in_(ids), Meeting.deleted_at.is_(None))
                .group_by(Meeting.scholar_id)
            )
        ).all()
    )
    quiet_since = today - timedelta(days=QUIET_DAYS)
    for s, _ in current:
        last = last_meeting.get(s.id)
        settled = s.admission_date is None or s.admission_date < quiet_since
        if settled and (last is None or last < quiet_since):
            reasons[s.id].append(
                f"No supervision meeting logged since {last:%d %b %Y}"
                if last
                else "No supervision meeting logged yet"
            )
    out = [
        {
            "scholar": {"id": s.id, "name": name},
            "stage": s.stage,
            "limit_date": assessed[s.id]["limit_date"],
            "reasons": reasons[s.id],
        }
        for s, name in current
        if reasons[s.id]
    ]
    out.sort(key=lambda r: (-len(r["reasons"]), r["scholar"]["name"]))
    return out[:RISK_LIMIT]
