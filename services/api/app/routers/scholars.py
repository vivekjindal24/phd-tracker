"""Scholar directory (PRD F6, UX Flow 5). Lists and details are scoped by scope.py."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import directory, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.enums import Stage
from app.errors import forbidden
from app.models import Faculty, OrgUnit, Scholar, User
from app.rbac import require_perm
from app.schemas import AssignIn, Ref, ScholarOut, ScholarUpdate

router = APIRouter(prefix="/scholars", tags=["directory"])

SupFaculty = aliased(Faculty)
SupUser = aliased(User)
CoFaculty = aliased(Faculty)
CoUser = aliased(User)


def _query(principal: Principal) -> Select:
    return (
        select(
            Scholar, User.full_name, User.email, OrgUnit.name, SupUser.full_name, CoUser.full_name
        )
        .join(User, User.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .outerjoin(SupFaculty, SupFaculty.id == Scholar.supervisor_id)
        .outerjoin(SupUser, SupUser.id == SupFaculty.user_id)
        .outerjoin(CoFaculty, CoFaculty.id == Scholar.co_supervisor_id)
        .outerjoin(CoUser, CoUser.id == CoFaculty.user_id)
        .where(Scholar.deleted_at.is_(None), scope.scholar_predicate(principal, "scholars"))
    )


def _out(row, co_supervision: str) -> ScholarOut:
    s, name, email, unit_name, sup_name, co_name = row
    return ScholarOut(
        id=s.id,
        user_id=s.user_id,
        full_name=name,
        email=email,
        roll_number=s.roll_number,
        unit=Ref(id=s.unit_id, name=unit_name),
        stage=s.stage,
        research_title=s.research_title,
        admission_date=s.admission_date,
        supervisor=Ref(id=s.supervisor_id, name=sup_name) if s.supervisor_id else None,
        co_supervisor=(
            Ref(id=s.co_supervisor_id, name=co_name)
            if s.co_supervisor_id and co_supervision != "off"
            else None
        ),
    )


async def _one(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> ScholarOut:
    row = (await session.execute(_query(principal).where(Scholar.id == scholar_id))).first()
    if row is None:
        raise forbidden()
    return _out(row, principal.co_supervision)


@router.get("", response_model=list[ScholarOut])
async def list_scholars(
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    stage: Stage | None = None,
    supervisor_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ScholarOut]:
    stmt = _query(principal)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            User.full_name.ilike(like)
            | Scholar.roll_number.ilike(like)
            | Scholar.research_title.ilike(like)
        )
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Scholar.unit_id.in_(scope.subtree_unit_ids((path,))))
    if stage:
        stmt = stmt.where(Scholar.stage == stage)
    if supervisor_id:
        stmt = stmt.where(Scholar.supervisor_id == supervisor_id)
    rows = await session.execute(stmt.order_by(User.full_name).limit(limit).offset(offset))
    return [_out(r, principal.co_supervision) for r in rows]


@router.get("/{scholar_id}", response_model=ScholarOut)
async def get_scholar(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    return await _one(session, principal, scholar_id)


@router.patch("/{scholar_id}", response_model=ScholarOut)
async def update_scholar(
    scholar_id: uuid.UUID,
    body: ScholarUpdate,
    principal: Principal = Depends(require_perm("scholars", "update")),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    await directory.require_admin_over_scholar(session, principal, scholar)
    changes = body.model_dump(exclude_unset=True)
    if "unit_id" in changes:  # moving a scholar needs admin over the destination too
        scope.require_admin_over(principal, await scope.unit_path(session, changes["unit_id"]))
    await update(session, principal, scholar, changes)
    await session.commit()
    return await _one(session, principal, scholar_id)


@router.put("/{scholar_id}/supervisor", response_model=ScholarOut)
async def set_supervisor(
    scholar_id: uuid.UUID,
    body: AssignIn,
    principal: Principal = Depends(require_perm("scholars", "assign_supervisor")),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    await directory.assign_supervisor(session, principal, scholar, body.faculty_id)
    await session.commit()
    return await _one(session, principal, scholar_id)


@router.put("/{scholar_id}/co-supervisor", response_model=ScholarOut)
async def set_co_supervisor(
    scholar_id: uuid.UUID,
    body: AssignIn,
    principal: Principal = Depends(require_perm("scholars", "assign_supervisor")),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    await directory.assign_co_supervisor(session, principal, scholar, body.faculty_id)
    await session.commit()
    return await _one(session, principal, scholar_id)
