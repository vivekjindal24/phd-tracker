"""The UGC maximum-duration rule (PRD Phase 4): warn before it is broken, not after.

limit = admission date + max years + approved extensions + relaxation. Leave is recorded and
checked against its own limit. The rule stops mattering once the thesis is submitted, the
degree awarded, or the scholar has left. One pure function decides — the profile, the
dashboards and the leadership view all call it."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import STAGES
from app.models import Scholar, Settings, TimeAdjustment

NEAR_LIMIT_DAYS = 180  # "nearing the limit" six months ahead
DONE_STAGES = frozenset(STAGES[STAGES.index("Thesis Submitted") :])


@dataclass(frozen=True)
class Limits:
    max_years: int
    max_extension_days: int
    max_relaxation_days: int
    max_maternity_leave_days: int


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def assess(
    scholar: Scholar, adjustments: Iterable[TimeAdjustment], limits: Limits, today: date
) -> dict:
    days = defaultdict(int)
    for a in adjustments:
        days[a.kind] += a.days
    warnings = []
    if days["extension"] > limits.max_extension_days:
        warnings.append(
            f"Extensions total {days['extension']} days; the limit is {limits.max_extension_days}"
        )
    if days["relaxation"] > limits.max_relaxation_days:
        warnings.append(
            f"Relaxation totals {days['relaxation']} days; the limit is "
            f"{limits.max_relaxation_days}"
        )
    if days["maternity_leave"] > limits.max_maternity_leave_days:
        warnings.append(
            f"Maternity / child-care leave totals {days['maternity_leave']} days; the limit is "
            f"{limits.max_maternity_leave_days}"
        )
    limit_date = days_left = None
    if scholar.admission_date is not None:
        limit_date = _add_years(scholar.admission_date, limits.max_years) + timedelta(
            days=days["extension"] + days["relaxation"]
        )
        days_left = (limit_date - today).days
    if scholar.left_on is not None:
        status = "left"
    elif scholar.stage in DONE_STAGES:
        status = "done"
    elif days_left is None:
        status = "unknown"  # no admission date recorded
    elif days_left < 0:
        status = "over"
        warnings.insert(0, f"Past the maximum duration since {limit_date:%d %b %Y}")
    elif days_left <= NEAR_LIMIT_DAYS:
        status = "near"
        warnings.insert(0, f"{days_left} days left before the maximum duration")
    else:
        status = "ok"
    return {
        "admission_date": scholar.admission_date,
        "limit_date": limit_date,
        "days_left": days_left,
        "status": status,
        "extension_days": days["extension"],
        "relaxation_days": days["relaxation"],
        "leave_days": days["maternity_leave"] + days["medical_leave"] + days["other_leave"],
        "warnings": warnings,
    }


async def limits(session: AsyncSession) -> Limits:
    row = await session.get(Settings, 1)
    assert row is not None, "settings row is seeded by migration 0001"
    return Limits(
        row.max_duration_years,
        row.max_extension_days,
        row.max_relaxation_days,
        row.max_maternity_leave_days,
    )


async def adjustments_for(
    session: AsyncSession, scholar_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[TimeAdjustment]]:
    out: dict[uuid.UUID, list[TimeAdjustment]] = defaultdict(list)
    for a in await session.scalars(
        select(TimeAdjustment)
        .where(
            TimeAdjustment.scholar_id.in_(list(scholar_ids)), TimeAdjustment.deleted_at.is_(None)
        )
        .order_by(TimeAdjustment.start_date)
    ):
        out[a.scholar_id].append(a)
    return out


async def assess_many(
    session: AsyncSession, scholars: list[Scholar], today: date
) -> dict[uuid.UUID, dict]:
    lim = await limits(session)
    adj = await adjustments_for(session, [s.id for s in scholars])
    return {s.id: assess(s, adj.get(s.id, []), lim, today) for s in scholars}
