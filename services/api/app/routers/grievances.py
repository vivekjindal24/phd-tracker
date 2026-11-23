"""Grievances (grievances.py): file, read, and each step of the case."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import grievances
from app.auth.principal import Principal
from app.db import get_session
from app.enums import GrievanceStatus
from app.models import Grievance
from app.rbac import require_perm
from app.schemas import GrievanceAppealIn, GrievanceDecisionIn, GrievanceIn, GrievanceView
from app.sorting import page_of

router = APIRouter(prefix="/grievances", tags=["grievances"])
CAN_READ = require_perm("grievances", "read")
CAN_ACT = require_perm("grievances", "update")


@router.get("", response_model=list[GrievanceView])
async def list_grievances(
    response: Response,
    status: GrievanceStatus | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(Grievance).where(
        Grievance.deleted_at.is_(None),
        grievances.visible(principal, await grievances.appeals_to(session)),
    )
    if status:
        stmt = stmt.where(Grievance.status == status)
    stmt = stmt.order_by(Grievance.created_at.desc(), Grievance.id)
    rows = (await page_of(session, response, stmt, limit, offset)).scalars().all()
    return [await grievances.view(session, principal, g) for g in rows]


@router.post("", response_model=GrievanceView, status_code=201)
async def file_grievance(
    body: GrievanceIn,
    principal: Principal = Depends(require_perm("grievances", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    g = await grievances.file(session, principal, body.model_dump())
    await session.commit()
    return await grievances.view(session, principal, g)


@router.get("/{grievance_id}", response_model=GrievanceView)
async def get_grievance(
    grievance_id: uuid.UUID,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    g = await grievances.get_or_403(session, principal, grievance_id)
    return await grievances.view(session, principal, g)


async def _step(session: AsyncSession, principal: Principal, gid: uuid.UUID, act) -> dict:
    g = await grievances.get_or_403(session, principal, gid)
    await act(g)
    await session.commit()
    return await grievances.view(session, principal, g)


@router.post("/{grievance_id}/decide", response_model=GrievanceView)
async def decide(
    grievance_id: uuid.UUID,
    body: GrievanceDecisionIn,
    principal: Principal = Depends(CAN_ACT),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _step(
        session,
        principal,
        grievance_id,
        lambda g: grievances.decide(session, principal, g, body.text),
    )


@router.post("/{grievance_id}/withdraw", response_model=GrievanceView)
async def withdraw(
    grievance_id: uuid.UUID,
    principal: Principal = Depends(CAN_ACT),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _step(
        session, principal, grievance_id, lambda g: grievances.withdraw(session, principal, g)
    )


@router.post("/{grievance_id}/accept", response_model=GrievanceView)
async def accept(
    grievance_id: uuid.UUID,
    principal: Principal = Depends(CAN_ACT),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _step(
        session, principal, grievance_id, lambda g: grievances.accept(session, principal, g)
    )


@router.post("/{grievance_id}/appeal", response_model=GrievanceView)
async def appeal(
    grievance_id: uuid.UUID,
    body: GrievanceAppealIn,
    principal: Principal = Depends(CAN_ACT),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _step(
        session,
        principal,
        grievance_id,
        lambda g: grievances.appeal(session, principal, g, body.reason),
    )


@router.post("/{grievance_id}/appeal-decision", response_model=GrievanceView)
async def decide_appeal(
    grievance_id: uuid.UUID,
    body: GrievanceDecisionIn,
    principal: Principal = Depends(CAN_ACT),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _step(
        session,
        principal,
        grievance_id,
        lambda g: grievances.decide_appeal(session, principal, g, body.text),
    )
