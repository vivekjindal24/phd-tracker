"""Research Advisory Committee per scholar (PRD F9b): its formations, each a dated version
with members and their roles. A record, not an approval step: kept by an admin over the
scholar's unit or the Research Office, like the register. Only the current (latest)
formation changes; earlier ones are frozen history."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import committee, scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import CommitteeFormation, CommitteeMember, Faculty, Scholar
from app.rbac import require_perm
from app.schemas.administration import (
    CommitteeMemberIn,
    CommitteeRoleIn,
    CommitteeView,
    FormationIn,
)

router = APIRouter(tags=["committee"])
ENTITY = "committee_members"


async def _view(session: AsyncSession, principal: Principal, scholar: Scholar) -> dict[str, Any]:
    return {
        "convener": await committee.convener(session, scholar),
        "formations": await committee.formations(session, scholar.id),
        "can_manage": await scope.can_record(session, principal, scholar),
    }


async def _writable(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> Scholar:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    if not await scope.can_record(session, principal, scholar):
        raise forbidden()
    return scholar


async def _current_formation(
    session: AsyncSession, principal: Principal, formation_id: uuid.UUID
) -> tuple[Scholar, CommitteeFormation]:
    """A formation the caller may change: it must be the scholar's current one."""
    formation = await session.scalar(
        select(CommitteeFormation).where(
            CommitteeFormation.id == formation_id, CommitteeFormation.deleted_at.is_(None)
        )
    )
    if formation is None:
        raise forbidden()
    scholar = await _writable(session, principal, formation.scholar_id)
    latest = await committee.current(session, scholar.id)
    if latest is None or latest.id != formation.id:
        raise ApiError(
            409, "formation_superseded", "An earlier committee is history; change the current one."
        )
    return scholar, formation


async def _live_member(session: AsyncSession, member_id: uuid.UUID) -> CommitteeMember:
    row = await session.scalar(
        select(CommitteeMember).where(
            CommitteeMember.id == member_id, CommitteeMember.deleted_at.is_(None)
        )
    )
    if row is None:
        raise forbidden()
    return row


def _check_order(formation: FormationIn, previous: CommitteeFormation | None) -> None:
    if previous is not None and formation.formed_on < previous.formed_on:
        raise ApiError(
            422, "formation_out_of_order", "A new committee cannot be formed before the last one."
        )


@router.get("/scholars/{scholar_id}/committee", response_model=CommitteeView)
async def get_committee(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    return await _view(session, principal, scholar)


@router.post("/scholars/{scholar_id}/committee/formations", response_model=CommitteeView)
async def form_committee(
    scholar_id: uuid.UUID,
    body: FormationIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Form the committee, or re-form it: the new version starts as a copy of the current
    members, to be changed from there."""
    scholar = await _writable(session, principal, scholar_id)
    previous = await committee.current(session, scholar.id)
    _check_order(body, previous)
    formation = await insert(
        session,
        principal,
        CommitteeFormation(
            scholar_id=scholar.id, secretary_id=scholar.supervisor_id, **body.model_dump()
        ),
    )
    if previous is not None:
        for m in await session.scalars(
            select(CommitteeMember).where(
                CommitteeMember.formation_id == previous.id, CommitteeMember.deleted_at.is_(None)
            )
        ):
            await insert(
                session,
                principal,
                CommitteeMember(
                    scholar_id=scholar.id,
                    formation_id=formation.id,
                    faculty_id=m.faculty_id,
                    name=m.name,
                    institution=m.institution,
                    role=m.role,
                ),
            )
    await session.commit()
    return await _view(session, principal, scholar)


@router.patch("/committee-formations/{formation_id}", response_model=CommitteeView)
async def correct_formation(
    formation_id: uuid.UUID,
    body: FormationIn,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar, formation = await _current_formation(session, principal, formation_id)
    earlier = await session.scalar(
        select(CommitteeFormation)
        .where(
            CommitteeFormation.scholar_id == scholar.id,
            CommitteeFormation.id != formation.id,
            CommitteeFormation.deleted_at.is_(None),
        )
        .order_by(CommitteeFormation.formed_on.desc(), CommitteeFormation.created_at.desc())
        .limit(1)
    )
    _check_order(body, earlier)
    await update(session, principal, formation, body.model_dump())
    await session.commit()
    return await _view(session, principal, scholar)


@router.delete("/committee-formations/{formation_id}", response_model=CommitteeView)
async def withdraw_formation(
    formation_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Withdraw a version recorded by mistake; the one before it is current again."""
    scholar, formation = await _current_formation(session, principal, formation_id)
    for m in await session.scalars(
        select(CommitteeMember).where(
            CommitteeMember.formation_id == formation.id, CommitteeMember.deleted_at.is_(None)
        )
    ):
        await soft_delete(session, principal, m)
    await soft_delete(session, principal, formation)
    await session.commit()
    return await _view(session, principal, scholar)


@router.post("/committee-formations/{formation_id}/members", response_model=CommitteeView)
async def add_member(
    formation_id: uuid.UUID,
    body: CommitteeMemberIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar, formation = await _current_formation(session, principal, formation_id)
    if body.faculty_id is not None:
        if body.faculty_id in (scholar.supervisor_id, formation.secretary_id):
            raise ApiError(
                409, "supervisor_is_convener", "The supervisor is already the secretary."
            )
        known = await session.scalar(
            select(Faculty.id).where(Faculty.id == body.faculty_id, Faculty.deleted_at.is_(None))
        )
        if known is None:
            raise ApiError(422, "faculty_not_found", "This faculty member does not exist.")
    await insert(
        session,
        principal,
        CommitteeMember(scholar_id=scholar.id, formation_id=formation.id, **body.model_dump()),
    )
    await session.commit()
    return await _view(session, principal, scholar)


@router.patch("/committee-members/{member_id}", response_model=CommitteeView)
async def change_role(
    member_id: uuid.UUID,
    body: CommitteeRoleIn,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _live_member(session, member_id)
    scholar, _ = await _current_formation(session, principal, row.formation_id)
    await update(session, principal, row, {"role": body.role})
    await session.commit()
    return await _view(session, principal, scholar)


@router.delete("/committee-members/{member_id}", response_model=CommitteeView)
async def remove_member(
    member_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _live_member(session, member_id)
    scholar, _ = await _current_formation(session, principal, row.formation_id)
    await soft_delete(session, principal, row)
    await session.commit()
    return await _view(session, principal, scholar)
