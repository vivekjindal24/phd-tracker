"""The RDC / committee register (PRD F9, UX Flow 6). Read follows scholar scope; writes by
the research office anywhere, or an admin over the scholar's unit."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import MilestoneStatus, MilestoneType
from app.errors import forbidden
from app.models import Milestone, OrgUnit, Scholar, User
from app.rbac import require_perm
from app.schemas import MilestoneIn, MilestoneOut, MilestoneUpdate, Ref

router = APIRouter(prefix="/milestones", tags=["register"])


def _query(principal: Principal) -> Select:
    return (
        select(Milestone, Scholar, User.full_name, OrgUnit.name)
        .join(Scholar, Scholar.id == Milestone.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .where(
            Milestone.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "milestones"),
        )
    )


def _out(row) -> MilestoneOut:
    m, scholar, name, unit_name = row
    return MilestoneOut(
        id=m.id,
        scholar=Ref(id=scholar.id, name=name),
        roll_number=scholar.roll_number,
        unit=Ref(id=scholar.unit_id, name=unit_name),
        milestone_type=m.milestone_type,
        status=m.status,
        approval_body=m.approval_body,
        resolution_number=m.resolution_number,
        resolution_date=m.resolution_date,
        notes=m.notes,
        updated_at=m.updated_at,
    )


async def _require_writer(session: AsyncSession, principal: Principal, scholar: Scholar) -> None:
    if "research_office" in principal.office_roles:
        return
    scope.require_admin_over(principal, await scope.unit_path(session, scholar.unit_id))


async def _one(session: AsyncSession, principal: Principal, milestone_id: uuid.UUID):
    row = (await session.execute(_query(principal).where(Milestone.id == milestone_id))).first()
    if row is None:
        raise forbidden()
    return row


@router.get("", response_model=list[MilestoneOut])
async def list_milestones(
    scholar_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
    milestone_type: MilestoneType | None = None,
    status: MilestoneStatus | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_perm("milestones", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[MilestoneOut]:
    stmt = _query(principal)
    if scholar_id:
        stmt = stmt.where(Milestone.scholar_id == scholar_id)
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Scholar.unit_id.in_(scope.subtree_unit_ids((path,))))
    if milestone_type:
        stmt = stmt.where(Milestone.milestone_type == milestone_type)
    if status:
        stmt = stmt.where(Milestone.status == status)
    rows = await session.execute(
        stmt.order_by(Milestone.resolution_date.desc().nulls_last(), Milestone.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_out(r) for r in rows]


@router.post("", response_model=MilestoneOut, status_code=201)
async def create_milestone(
    body: MilestoneIn,
    principal: Principal = Depends(require_perm("milestones", "create")),
    session: AsyncSession = Depends(get_session),
) -> MilestoneOut:
    scholar = await scope.get_scholar_or_403(session, principal, body.scholar_id, "milestones")
    await _require_writer(session, principal, scholar)
    m = await insert(session, principal, Milestone(**body.model_dump()))
    await session.commit()
    return _out(await _one(session, principal, m.id))


@router.patch("/{milestone_id}", response_model=MilestoneOut)
async def update_milestone(
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    principal: Principal = Depends(require_perm("milestones", "update")),
    session: AsyncSession = Depends(get_session),
) -> MilestoneOut:
    m, scholar, *_ = await _one(session, principal, milestone_id)
    await _require_writer(session, principal, scholar)
    await update(session, principal, m, body.model_dump(exclude_unset=True))
    await session.commit()
    return _out(await _one(session, principal, milestone_id))


@router.delete("/{milestone_id}", status_code=204)
async def delete_milestone(
    milestone_id: uuid.UUID,
    principal: Principal = Depends(require_perm("milestones", "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    m, scholar, *_ = await _one(session, principal, milestone_id)
    await _require_writer(session, principal, scholar)
    await soft_delete(session, principal, m)
    await session.commit()
