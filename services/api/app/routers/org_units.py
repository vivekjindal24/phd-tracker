import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import org
from app.auth.deps import current_principal, require_root_admin
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.models import OrgUnit
from app.schemas import OrgUnitCreate, OrgUnitOut, OrgUnitUpdate

router = APIRouter(prefix="/org-units", tags=["org"])


@router.get("", response_model=list[OrgUnitOut])
async def list_units(
    _: Principal = Depends(current_principal), session: AsyncSession = Depends(get_session)
) -> list[OrgUnit]:
    """The tree is readable by every signed-in user (structure is not sensitive)."""
    rows = await session.scalars(
        select(OrgUnit).where(OrgUnit.deleted_at.is_(None)).order_by(OrgUnit.path)
    )
    return list(rows)


@router.post("", response_model=OrgUnitOut, status_code=201)
async def create_unit(
    body: OrgUnitCreate,
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> OrgUnit:
    parent = await org.get_unit(session, body.parent_id)
    unit = await org.create_unit(session, principal, parent, body.name, body.kind, body.code)
    await session.commit()
    return unit


@router.patch("/{unit_id}", response_model=OrgUnitOut)
async def update_unit(
    unit_id: uuid.UUID,
    body: OrgUnitUpdate,
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> OrgUnit:
    unit = await org.get_unit(session, unit_id)
    changes = body.model_dump(exclude_unset=True, exclude={"parent_id"})
    await update(session, principal, unit, changes)
    if body.parent_id is not None and body.parent_id != unit.parent_id:
        await org.move_unit(session, principal, unit, await org.get_unit(session, body.parent_id))
    await session.commit()
    return unit


@router.delete("/{unit_id}", status_code=204)
async def delete_unit(
    unit_id: uuid.UUID,
    principal: Principal = Depends(require_root_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    await org.delete_unit(session, principal, await org.get_unit(session, unit_id))
    await session.commit()
