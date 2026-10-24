"""Coursework rules (PRD M4 + Phase 4 UGC rules). One computation of credits and CGPA, used to
warn early (the coursework view) and to refuse a clearance that would break the rule (submit)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.crud import update
from app.models import Course, CourseworkClearance, Enrolment, Settings
from app.workflow import ItemContext, violation

LOCKED_STATES = ("in_review", "approved")


async def rules(session: AsyncSession) -> tuple[float, float]:
    row = await session.get(Settings, 1)
    assert row is not None, "settings row is seeded by migration 0001"
    return row.min_coursework_credits, row.min_coursework_cgpa


async def enrolments(
    session: AsyncSession, scholar_id: uuid.UUID
) -> list[tuple[Enrolment, Course]]:
    rows = await session.execute(
        select(Enrolment, Course)
        .join(Course, Course.id == Enrolment.course_id)
        .where(Enrolment.scholar_id == scholar_id, Enrolment.deleted_at.is_(None))
        .order_by(Enrolment.semester, Course.code)
    )
    return [(e, c) for e, c in rows]


def problems(
    credits: float, cgpa: float | None, ungraded: int, min_credits: float, min_cgpa: float
) -> list[str]:
    """What stands between this record and clearance — empty when it may be cleared."""
    out = []
    if ungraded:
        out.append(f"{ungraded} course{'s' if ungraded > 1 else ''} still without a grade")
    if credits < min_credits:
        out.append(f"{credits:g} credits graded; the minimum is {min_credits:g}")
    if cgpa is not None and cgpa < min_cgpa:
        out.append(f"CGPA {cgpa:.2f} is below the minimum {min_cgpa:.2f}")
    return out


async def summary(session: AsyncSession, scholar_id: uuid.UUID) -> dict[str, Any]:
    rows = await enrolments(session, scholar_id)
    graded = [(e, c) for e, c in rows if e.grade_points is not None]
    credits = sum(c.credits for _, c in graded)
    cgpa = (
        round(sum(c.credits * e.grade_points for e, c in graded) / credits, 2) if credits else None
    )
    min_credits, min_cgpa = await rules(session)
    return {
        "rows": rows,
        "credits": credits,
        "cgpa": cgpa,
        "min_credits": min_credits,
        "min_cgpa": min_cgpa,
        "problems": problems(credits, cgpa, len(rows) - len(graded), min_credits, min_cgpa),
    }


async def clearance(session: AsyncSession, scholar_id: uuid.UUID) -> CourseworkClearance | None:
    return await session.scalar(
        select(CourseworkClearance).where(
            CourseworkClearance.scholar_id == scholar_id, CourseworkClearance.deleted_at.is_(None)
        )
    )


async def require_unlocked(session: AsyncSession, scholar_id: uuid.UUID) -> None:
    """Grades are frozen while a clearance is in review or once it is approved."""
    c = await clearance(session, scholar_id)
    if c is not None and c.state in LOCKED_STATES:
        raise violation("Coursework is locked while its clearance is in review or approved.")


async def check_and_compute(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    """Before submit: refuse what would break the rule; record what is being certified."""
    s = await summary(session, ctx.scholar.id)
    if not s["rows"]:
        raise violation("Enrol the scholar in their courses before submitting for clearance.")
    if s["problems"]:
        raise violation("Coursework cannot be cleared yet: " + "; ".join(s["problems"]) + ".")
    await update(session, principal, ctx.item, {"credits": s["credits"], "cgpa": s["cgpa"]})


async def mark_cleared(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    await update(session, principal, ctx.item, {"cleared_on": datetime.now(UTC).date()})
