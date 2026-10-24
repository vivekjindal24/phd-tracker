"""Faculty directory (PRD F6): readable by every role — a university's faculty list is public
inside it. Edits need an admin over the faculty member's unit."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import directory, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.enums import UGC_CAP
from app.errors import forbidden
from app.models import Faculty, OrgUnit, User
from app.rbac import require_perm
from app.schemas import FacultyOut, FacultyUpdate, Ref

router = APIRouter(prefix="/faculty", tags=["directory"])

_load = directory.load_of_faculty()


def _query() -> Select:
    return (
        select(Faculty, User.full_name, User.email, OrgUnit.name, _load)
        .join(User, User.id == Faculty.user_id)
        .join(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .where(Faculty.deleted_at.is_(None))
    )


def _out(row) -> FacultyOut:
    f, name, email, unit_name, load = row
    return FacultyOut(
        id=f.id,
        user_id=f.user_id,
        full_name=name,
        email=email,
        unit=Ref(id=f.unit_id, name=unit_name),
        designation=f.designation,
        employee_id=f.employee_id,
        can_supervise=f.can_supervise,
        max_scholars=f.max_scholars,
        load=load,
    )


@router.get("", response_model=list[FacultyOut])
async def list_faculty(
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    can_supervise: bool | None = None,
    with_capacity: bool = False,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[FacultyOut]:
    stmt = _query()
    if q:
        stmt = stmt.where(User.full_name.ilike(f"%{q}%"))
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Faculty.unit_id.in_(scope.subtree_unit_ids((path,))))
    if can_supervise is not None:
        stmt = stmt.where(Faculty.can_supervise.is_(can_supervise))
    if with_capacity:  # supervisor pickers list only people below their cap
        stmt = stmt.where(_load < Faculty.max_scholars)
    rows = await session.execute(stmt.order_by(User.full_name).limit(limit).offset(offset))
    return [_out(r) for r in rows]


@router.get("/{faculty_id}", response_model=FacultyOut)
async def get_faculty(
    faculty_id: uuid.UUID,
    _: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> FacultyOut:
    row = (await session.execute(_query().where(Faculty.id == faculty_id))).first()
    if row is None:
        raise forbidden()
    return _out(row)


@router.patch("/{faculty_id}", response_model=FacultyOut)
async def update_faculty(
    faculty_id: uuid.UUID,
    body: FacultyUpdate,
    principal: Principal = Depends(require_perm("faculty", "update")),
    session: AsyncSession = Depends(get_session),
) -> FacultyOut:
    faculty = await session.scalar(
        select(Faculty).where(Faculty.id == faculty_id, Faculty.deleted_at.is_(None))
    )
    if faculty is None:
        raise forbidden()
    scope.require_admin_over(principal, await scope.unit_path(session, faculty.unit_id))
    changes = body.model_dump(exclude_unset=True)
    if "unit_id" in changes:
        scope.require_admin_over(principal, await scope.unit_path(session, changes["unit_id"]))
    designation = changes.get("designation", faculty.designation)
    max_scholars = changes.get("max_scholars", faculty.max_scholars)
    if "designation" in changes and "max_scholars" not in changes:
        max_scholars = changes["max_scholars"] = UGC_CAP[designation]  # same default as create
    directory.validate_faculty_cap(designation, max_scholars)
    await update(session, principal, faculty, changes)
    await session.commit()
    return await get_faculty(faculty_id, principal, session)
