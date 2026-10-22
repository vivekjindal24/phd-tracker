"""Seminar grading rules (PRD F15, SECURITY.md §3 "Seminar grading")."""

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import seminars
from app.auth.principal import Principal
from app.errors import ApiError, forbidden
from app.models import Scholar, Seminar, SeminarPanel, SeminarScholar


async def is_grader(session: AsyncSession, principal: Principal, seminar_id: uuid.UUID) -> bool:
    if principal.faculty_id is None:
        return False
    row = await session.scalar(
        select(SeminarPanel.id).where(
            SeminarPanel.seminar_id == seminar_id,
            SeminarPanel.faculty_id == principal.faculty_id,
            SeminarPanel.deleted_at.is_(None),
        )
    )
    return row is not None


def can_finalise(principal: Principal, scholar: Scholar) -> bool:
    fid = principal.faculty_id
    return fid is not None and (
        fid == scholar.supervisor_id
        or (principal.co_supervision == "approve" and fid == scholar.co_supervisor_id)
    )


def supervises(principal: Principal, scholar: Scholar) -> bool:
    fid = principal.faculty_id
    return fid is not None and (
        fid == scholar.supervisor_id
        or (principal.co_supervision != "off" and fid == scholar.co_supervisor_id)
    )


async def load_entry(
    session: AsyncSession, seminar_id: uuid.UUID, scholar_id: uuid.UUID
) -> tuple[SeminarScholar, Scholar]:
    row = (
        await session.execute(
            select(SeminarScholar, Scholar)
            .join(Scholar, Scholar.id == SeminarScholar.scholar_id)
            .where(
                SeminarScholar.seminar_id == seminar_id,
                SeminarScholar.scholar_id == scholar_id,
                SeminarScholar.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise ApiError(422, "not_in_seminar", "This scholar is not part of the seminar.")
    return row[0], row[1]


async def require_review_access(
    session: AsyncSession,
    principal: Principal,
    seminar: Seminar,
    unit_path: str,
    entry: SeminarScholar,
    scholar: Scholar,
) -> None:
    """Department, research office, graders and supervisors read the review any time;
    the scholar only after their supervisor finalised it."""
    if (
        seminars.can_manage(principal, unit_path)
        or "research_office" in principal.office_roles
        or supervises(principal, scholar)
        or await is_grader(session, principal, seminar.id)
    ):
        return
    if principal.scholar_id == scholar.id and entry.finalised_at is not None:
        return
    raise forbidden()


def validate_scores(rubric: list[dict[str, Any]], scores: dict[str, Any]) -> dict[str, float]:
    """Every rubric criterion scored, within 0..max, at most one decimal place."""
    names = [c["name"] for c in rubric]
    unknown = sorted(set(scores) - set(names))
    missing = [n for n in names if n not in scores]
    if unknown or missing:
        raise ApiError(
            422,
            "scores_mismatch",
            "Score every rubric criterion, and only those.",
            {"missing": missing, "unknown": unknown},
        )
    clean: dict[str, float] = {}
    for c in rubric:
        try:
            value = Decimal(str(scores[c["name"]]))
        except InvalidOperation as exc:
            raise ApiError(422, "score_invalid", f"{c['name']}: not a number.") from exc
        if not (0 <= value <= c["max"]) or value.as_tuple().exponent < -1:
            raise ApiError(
                422,
                "score_out_of_range",
                f"{c['name']} must be between 0 and {c['max']} (one decimal at most).",
            )
        clean[c["name"]] = float(value)
    return clean
