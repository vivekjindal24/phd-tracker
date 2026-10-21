"""Org-unit tree on ltree paths (ARCHITECTURE.md §6). Paths are maintained only here."""

import re
import uuid

from sqlalchemy import case, cast, exists, func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.crud import audit, insert, snapshot, soft_delete
from app.errors import ApiError
from app.models import Faculty, OrgUnit, Scholar
from app.models.base import Ltree


def path_label(code: str) -> str:
    """ltree labels allow [A-Za-z0-9_]; unit codes also allow '-'."""
    return re.sub(r"[^a-z0-9_]", "_", code.lower())


async def get_unit(session: AsyncSession, unit_id: uuid.UUID) -> OrgUnit:
    unit = await session.scalar(
        select(OrgUnit).where(OrgUnit.id == unit_id, OrgUnit.deleted_at.is_(None))
    )
    if unit is None:
        raise ApiError(404, "unit_not_found", "This unit does not exist.")
    return unit


async def create_unit(
    session: AsyncSession,
    principal: Principal | None,
    parent: OrgUnit | None,
    name: str,
    kind: str,
    code: str,
) -> OrgUnit:
    label = path_label(code)
    path = f"{parent.path}.{label}" if parent else label
    return await insert(
        session,
        principal,
        OrgUnit(
            parent_id=parent.id if parent else None,
            name=name,
            kind=kind,
            code=code,
            path=path,
        ),
    )


async def move_unit(
    session: AsyncSession, principal: Principal, unit: OrgUnit, new_parent: OrgUnit
) -> None:
    """Re-parent a unit and rewrite every descendant's path in one statement."""
    if unit.parent_id is None:
        raise ApiError(422, "cannot_move_root", "The university root cannot be moved.")
    if new_parent.path == unit.path or new_parent.path.startswith(unit.path + "."):
        raise ApiError(422, "invalid_move", "A unit cannot be moved inside itself.")
    prev = snapshot(unit)
    old_path = unit.path
    new_path = f"{new_parent.path}.{path_label(unit.code)}"
    old = cast(literal(old_path), Ltree)
    await session.execute(
        update(OrgUnit)
        .where(OrgUnit.path.op("<@")(old))
        .values(
            path=case(  # ltree has no empty slice: the moved unit itself is its own branch
                (OrgUnit.path == old, cast(literal(new_path), Ltree)),
                else_=cast(literal(new_path), Ltree).op("||")(
                    func.subpath(OrgUnit.path, func.nlevel(old))
                ),
            )
        )
        .execution_options(synchronize_session=False)
    )
    await session.execute(
        update(OrgUnit)
        .where(OrgUnit.id == unit.id)
        .values(parent_id=new_parent.id)
        .execution_options(synchronize_session=False)
    )
    await session.flush()
    await session.refresh(unit)
    audit(session, principal, unit, "update", prev=prev)


async def delete_unit(session: AsyncSession, principal: Principal, unit: OrgUnit) -> None:
    if unit.parent_id is None:
        raise ApiError(422, "cannot_delete_root", "The university root cannot be deleted.")
    occupied = await session.scalar(
        select(
            exists().where(OrgUnit.parent_id == unit.id, OrgUnit.deleted_at.is_(None))
            | exists().where(Scholar.unit_id == unit.id, Scholar.deleted_at.is_(None))
            | exists().where(Faculty.unit_id == unit.id, Faculty.deleted_at.is_(None))
        )
    )
    if occupied:
        raise ApiError(
            409, "unit_not_empty", "Move or remove its sub-units, scholars and faculty first."
        )
    await soft_delete(session, principal, unit)
