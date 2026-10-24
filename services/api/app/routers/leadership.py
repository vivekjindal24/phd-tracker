"""The leadership view (PRD Phase 4) for one unit's subtree: heads and admins for their units,
the research office and root admin for any unit (the university by default)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import leadership
from app.auth.principal import Principal
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import OrgUnit
from app.rbac import require_perm
from app.schemas import LeadershipView

router = APIRouter(tags=["leadership"])


def _sees_everything(principal: Principal) -> bool:
    return principal.is_root_admin or "research_office" in principal.office_roles


@router.get("/leadership", response_model=LeadershipView)
async def get_leadership(
    unit_id: uuid.UUID | None = None,
    principal: Principal = Depends(require_perm("leadership", "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if unit_id is None:
        if _sees_everything(principal):
            unit = await session.scalar(
                select(OrgUnit).where(OrgUnit.parent_id.is_(None), OrgUnit.deleted_at.is_(None))
            )
        else:  # a head / admin: their highest unit
            top = min(principal.unit_roles, key=lambda r: r.unit_path.count("."))
            unit = await session.get(OrgUnit, top.unit_id)
        if unit is None:
            raise ApiError(404, "no_university", "The university tree is not set up yet.")
    else:
        unit = await session.scalar(
            select(OrgUnit).where(OrgUnit.id == unit_id, OrgUnit.deleted_at.is_(None))
        )
        if unit is None:
            raise forbidden()
    if not (
        _sees_everything(principal)
        or principal.covers("unit_head", unit.path)
        or principal.covers("admin", unit.path)
    ):
        raise forbidden()
    return await leadership.build(session, unit)
