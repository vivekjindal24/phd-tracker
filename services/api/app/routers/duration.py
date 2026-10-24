"""UGC maximum duration (PRD Phase 4): each scholar's limit date with extensions, relaxation
and leave, warned about before it passes. Records are written by an admin over the scholar's
unit or by the research office, like the RDC register."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import duration, scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete
from app.db import get_session
from app.errors import forbidden
from app.models import Scholar, TimeAdjustment, User
from app.rbac import require_perm
from app.schemas import DurationView, TimeAdjustmentIn

router = APIRouter(tags=["duration"])


async def _may_write(session: AsyncSession, principal: Principal, scholar: Scholar) -> bool:
    if "research_office" in principal.office_roles:
        return True
    return principal.covers("admin", await scope.unit_path(session, scholar.unit_id))


async def _view(session: AsyncSession, principal: Principal, scholar: Scholar) -> dict[str, Any]:
    limits = await duration.limits(session)
    rows = (await duration.adjustments_for(session, [scholar.id])).get(scholar.id, [])
    assessed = duration.assess(scholar, rows, limits, datetime.now(UTC).date())
    name = await session.scalar(select(User.full_name).where(User.id == scholar.user_id))
    return {
        **assessed,
        "scholar": {"id": scholar.id, "name": name},
        "adjustments": [
            {
                "id": a.id,
                "kind": a.kind,
                "start_date": a.start_date,
                "end_date": a.end_date,
                "days": a.days,
                "resolution_number": a.resolution_number,
                "notes": a.notes,
            }
            for a in rows
        ],
        "max_years": limits.max_years,
        "can_manage": await _may_write(session, principal, scholar),
    }


@router.get("/scholars/{scholar_id}/duration", response_model=DurationView)
async def get_duration(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(require_perm("time_adjustments", "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, "time_adjustments")
    return await _view(session, principal, scholar)


@router.post("/scholars/{scholar_id}/time-adjustments", response_model=DurationView)
async def add_adjustment(
    scholar_id: uuid.UUID,
    body: TimeAdjustmentIn,
    principal: Principal = Depends(require_perm("time_adjustments", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Recorded even when it goes past a limit — the view then says so; the university's
    committee, not the software, decides on exceptions."""
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, "time_adjustments")
    if not await _may_write(session, principal, scholar):
        raise forbidden()
    await insert(session, principal, TimeAdjustment(scholar_id=scholar.id, **body.model_dump()))
    await session.commit()
    return await _view(session, principal, scholar)


@router.delete("/time-adjustments/{adjustment_id}", response_model=DurationView)
async def remove_adjustment(
    adjustment_id: uuid.UUID,
    principal: Principal = Depends(require_perm("time_adjustments", "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(TimeAdjustment).where(
            TimeAdjustment.id == adjustment_id, TimeAdjustment.deleted_at.is_(None)
        )
    )
    if row is None:
        raise forbidden()
    scholar = await scope.get_scholar_or_403(session, principal, row.scholar_id, "time_adjustments")
    if not await _may_write(session, principal, scholar):
        raise forbidden()
    await soft_delete(session, principal, row)
    await session.commit()
    return await _view(session, principal, scholar)
