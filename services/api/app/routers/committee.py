"""Research Advisory Committee members per scholar (PRD F9b). A record, not an approval
step: kept by an admin over the scholar's unit or the Research Office, like the register."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import committee, scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import CommitteeMember, Faculty, Scholar
from app.rbac import require_perm
from app.schemas.administration import CommitteeMemberIn, CommitteeView

router = APIRouter(tags=["committee"])
ENTITY = "committee_members"


async def _view(session: AsyncSession, principal: Principal, scholar: Scholar) -> dict[str, Any]:
    return {
        "convener": await committee.convener(session, scholar),
        "members": await committee.members(session, scholar),
        "can_manage": await scope.can_record(session, principal, scholar),
    }


async def _writable(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> Scholar:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    if not await scope.can_record(session, principal, scholar):
        raise forbidden()
    return scholar


@router.get("/scholars/{scholar_id}/committee", response_model=CommitteeView)
async def get_committee(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    return await _view(session, principal, scholar)


@router.post("/scholars/{scholar_id}/committee", response_model=CommitteeView)
async def add_member(
    scholar_id: uuid.UUID,
    body: CommitteeMemberIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await _writable(session, principal, scholar_id)
    if body.faculty_id is not None:
        if body.faculty_id == scholar.supervisor_id:
            raise ApiError(
                409, "supervisor_is_convener", "The supervisor already convenes the committee."
            )
        known = await session.scalar(
            select(Faculty.id).where(Faculty.id == body.faculty_id, Faculty.deleted_at.is_(None))
        )
        if known is None:
            raise ApiError(422, "faculty_not_found", "This faculty member does not exist.")
    await insert(session, principal, CommitteeMember(scholar_id=scholar.id, **body.model_dump()))
    await session.commit()
    return await _view(session, principal, scholar)


@router.delete("/committee-members/{member_id}", response_model=CommitteeView)
async def remove_member(
    member_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(CommitteeMember).where(
            CommitteeMember.id == member_id, CommitteeMember.deleted_at.is_(None)
        )
    )
    if row is None:
        raise forbidden()
    scholar = await _writable(session, principal, row.scholar_id)
    await soft_delete(session, principal, row)
    await session.commit()
    return await _view(session, principal, scholar)
