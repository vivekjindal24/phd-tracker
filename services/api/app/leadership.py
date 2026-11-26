"""The leadership view (PRD Phase 4): scholars at risk, time to completion and drop-outs per
unit, supervisor load, and five years of trends. Computed for one unit's subtree; who may ask
is decided by the caller (routers/leadership.py) through the same covers() rules as every
other head/admin view."""

import statistics
import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import dashboard, dates, directory, duration, naac, returns, scope
from app.models import (
    Faculty,
    FacultyPublication,
    Meeting,
    Milestone,
    OrgUnit,
    Publication,
    Scholar,
    User,
)

QUIET_DAYS = 120  # no supervision meeting logged for four months
DAYS_PER_YEAR = 365.25
RISK_LIMIT = 50
TREND_YEARS = 5


def _in(path: str, unit_path: str) -> bool:
    return unit_path == path or unit_path.startswith(path + ".")


async def _awards(session: AsyncSession, units) -> dict[uuid.UUID, tuple[date | None, date]]:
    """Admission date and the day the degree was awarded (the register's approved decision),
    per completed scholar."""
    rows = await session.execute(
        select(Scholar.id, Scholar.admission_date, func.min(Milestone.resolution_date))
        .join(Milestone, Milestone.scholar_id == Scholar.id)
        .where(
            Scholar.unit_id.in_(units),
            Scholar.deleted_at.is_(None),
            Milestone.deleted_at.is_(None),
            Milestone.milestone_type == "degree_awarded",
            Milestone.status == "Approved",
            Milestone.resolution_date.is_not(None),
        )
        .group_by(Scholar.id, Scholar.admission_date)
    )
    return {sid: (admitted, awarded) for sid, admitted, awarded in rows}


def _years_taken(admitted: date | None, awarded: date) -> float | None:
    return None if admitted is None else (awarded - admitted).days / DAYS_PER_YEAR


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


async def _papers_by_year(session: AsyncSession, units, years: tuple[int, int]) -> Counter:
    """Published papers per calendar year: scholars' approved through their chain and
    faculty's verified by the Library, as NAAC counts them. One DOI is one paper."""
    scholars = await session.execute(
        select(Publication.pub_year, Publication.doi, Publication.id)
        .join(Scholar, Scholar.id == Publication.scholar_id)
        .where(
            Scholar.unit_id.in_(units),
            Publication.deleted_at.is_(None),
            Publication.state == "approved",
            Publication.pub_status == "published",
            Publication.pub_year.between(*years),
        )
    )
    faculty = await session.execute(
        select(FacultyPublication.pub_year, FacultyPublication.doi, FacultyPublication.id)
        .join(Faculty, Faculty.id == FacultyPublication.faculty_id)
        .where(
            Faculty.unit_id.in_(units),
            FacultyPublication.deleted_at.is_(None),
            FacultyPublication.verification == "verified",
            FacultyPublication.pub_status == "published",
            FacultyPublication.pub_year.between(*years),
        )
    )
    papers = {doi.lower() if doi else pid: y for y, doi, pid in [*scholars, *faculty]}
    return Counter(papers.values())


async def _trends(
    session: AsyncSession, units, scholars: list, awards: dict, today: date
) -> list[dict[str, Any]]:
    """The last five academic years, the current one so far. Papers carry only a calendar
    year, so a year's papers are counted in the academic year that starts in it."""
    current = today.year if today.month >= naac.AY_START_MONTH else today.year - 1
    starts = range(current - TREND_YEARS + 1, current + 1)
    papers = await _papers_by_year(session, units, (starts[0], starts[-1]))
    out = []
    for year in starts:
        lo, hi = returns.ay_bounds(year)
        done = [(admitted, awarded) for admitted, awarded in awards.values() if lo <= awarded <= hi]
        taken = [t for a, d in done if (t := _years_taken(a, d)) is not None]
        out.append(
            {
                "year": naac.academic_year(lo),
                "so_far": year == current,
                "admitted": sum(
                    s.admission_date is not None and lo <= s.admission_date <= hi for s in scholars
                ),
                "awarded": len(done),
                "median_years_to_complete": _median(taken),
                "publications": papers[year],
            }
        )
    return out


def _unit_row(unit: dict, scholars: list, years: dict, faculty: list) -> dict[str, Any]:
    current = [s for s in scholars if directory.counts_toward_cap(s)]
    completed = [s for s in scholars if s.stage == directory.COMPLETED_STAGE]
    left = [s for s in scholars if s.left_on is not None]
    known = [years[s.id] for s in completed if years.get(s.id) is not None]
    started = len(current) + len(completed) + len(left)
    loads = [load for _, load, _ in faculty]
    return {
        "unit": unit,
        "current": len(current),
        "completed": len(completed),
        "median_years_to_complete": _median(known),
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
    awards = await _awards(session, units)
    years = {sid: _years_taken(admitted, awarded) for sid, (admitted, awarded) in awards.items()}
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
        "trends": await _trends(session, units, [s for s, _, _ in scholar_rows], awards, today),
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
            f"Progress report overdue since {dates.day(row['report_due'])}"
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
                f"No supervision meeting logged since {dates.day(last)}"
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
