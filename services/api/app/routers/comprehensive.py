"""The comprehensive examination per scholar (Form VI; PRD F17): numbered attempts, each with
the month held and its result. A record kept by an admin over the scholar's unit or the
Research Office, like the register; a satisfactory attempt ends the attempts."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import ComprehensiveExam, Scholar
from app.rbac import require_perm
from app.schemas.administration import ComprehensiveIn, ComprehensiveView

router = APIRouter(tags=["comprehensive"])
ENTITY = "comprehensive_exams"


async def _attempts(session: AsyncSession, scholar_id: uuid.UUID) -> list[ComprehensiveExam]:
    return list(
        await session.scalars(
            select(ComprehensiveExam)
            .where(
                ComprehensiveExam.scholar_id == scholar_id,
                ComprehensiveExam.deleted_at.is_(None),
            )
            .order_by(ComprehensiveExam.attempt)
        )
    )


async def _view(session: AsyncSession, principal: Principal, scholar: Scholar) -> dict[str, Any]:
    attempts = await _attempts(session, scholar.id)
    return {
        "attempts": attempts,
        "passed": any(a.result == "satisfactory" for a in attempts),
        "can_manage": await scope.can_record(session, principal, scholar),
    }


async def _writable(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> Scholar:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    if not await scope.can_record(session, principal, scholar):
        raise forbidden()
    return scholar


@router.get("/scholars/{scholar_id}/comprehensive", response_model=ComprehensiveView)
async def get_comprehensive(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    return await _view(session, principal, scholar)


@router.post("/scholars/{scholar_id}/comprehensive", response_model=ComprehensiveView)
async def add_attempt(
    scholar_id: uuid.UUID,
    body: ComprehensiveIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await _writable(session, principal, scholar_id)
    attempts = await _attempts(session, scholar.id)
    if any(a.result == "satisfactory" for a in attempts):
        raise ApiError(
            409, "comprehensive_passed", "The comprehensive examination is already passed."
        )
    if attempts and body.held_in < attempts[-1].held_in:
        raise ApiError(
            422, "attempt_out_of_order", "An attempt cannot come before the previous one."
        )
    await insert(
        session,
        principal,
        ComprehensiveExam(scholar_id=scholar.id, attempt=len(attempts) + 1, **body.model_dump()),
    )
    await session.commit()
    return await _view(session, principal, scholar)


@router.delete("/comprehensive-exams/{attempt_id}", response_model=ComprehensiveView)
async def remove_attempt(
    attempt_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Remove an attempt recorded by mistake: only the latest, so the numbering holds."""
    row = await session.scalar(
        select(ComprehensiveExam).where(
            ComprehensiveExam.id == attempt_id, ComprehensiveExam.deleted_at.is_(None)
        )
    )
    if row is None:
        raise forbidden()
    scholar = await _writable(session, principal, row.scholar_id)
    if (await _attempts(session, scholar.id))[-1].id != row.id:
        raise ApiError(409, "not_latest_attempt", "Remove the latest attempt first.")
    await soft_delete(session, principal, row)
    await session.commit()
    return await _view(session, principal, scholar)
