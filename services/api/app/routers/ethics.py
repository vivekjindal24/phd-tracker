"""Research ethics clearance per scholar (PRD F9c). A record kept by an admin over the
scholar's unit or the Research Office, like the register; the thesis gate is in ethics.py."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ethics, scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import EthicsClearance, Scholar
from app.rbac import require_perm
from app.schemas.administration import EthicsIn, EthicsView

router = APIRouter(tags=["ethics"])
ENTITY = "ethics_clearances"


async def _view(session: AsyncSession, principal: Principal, scholar: Scholar) -> dict[str, Any]:
    rows = await ethics.records(session, scholar.id)
    return {
        "records": rows,
        "required": await ethics.required(session),
        "satisfied": bool(rows),
        "can_manage": await scope.can_record(session, principal, scholar),
    }


async def _writable(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> Scholar:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    if not await scope.can_record(session, principal, scholar):
        raise forbidden()
    return scholar


@router.get("/scholars/{scholar_id}/ethics", response_model=EthicsView)
async def get_ethics(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    return await _view(session, principal, scholar)


@router.post("/scholars/{scholar_id}/ethics", response_model=EthicsView)
async def add_record(
    scholar_id: uuid.UUID,
    body: EthicsIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await _writable(session, principal, scholar_id)
    existing = await ethics.records(session, scholar.id)
    # "Not required" and a clearance contradict each other: one must be removed first.
    if existing and (body.kind == "not_required") != (existing[0].kind == "not_required"):
        raise ApiError(
            409,
            "ethics_conflict",
            "This scholar has a clearance and cannot also be marked as needing none. "
            "Remove the entry that no longer applies first.",
        )
    if existing and body.kind == "not_required":
        raise ApiError(409, "ethics_conflict", "This is already recorded.")
    await insert(session, principal, EthicsClearance(scholar_id=scholar.id, **body.model_dump()))
    await session.commit()
    return await _view(session, principal, scholar)


@router.delete("/ethics-clearances/{record_id}", response_model=EthicsView)
async def remove_record(
    record_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(EthicsClearance).where(
            EthicsClearance.id == record_id, EthicsClearance.deleted_at.is_(None)
        )
    )
    if row is None:
        raise forbidden()
    scholar = await _writable(session, principal, row.scholar_id)
    await soft_delete(session, principal, row)
    await session.commit()
    return await _view(session, principal, scholar)
