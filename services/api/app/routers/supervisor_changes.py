"""Change of supervisor (supervisor_changes.py): the department admin proposes, edits or
withdraws it here; it is submitted and approved through /items like any other item."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import directory, items, scope, workflow
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.errors import ApiError
from app.models import Faculty, SupervisorChange, User
from app.rbac import require_perm
from app.schemas import ItemView, SupervisorChangeIn, SupervisorChangeUpdate
from app.workflow import ItemContext

router = APIRouter(tags=["supervision"])
ENTITY = "supervisor_changes"
KIND = "supervisor_change"


async def _name(session: AsyncSession, faculty_id: uuid.UUID | None) -> str | None:
    if faculty_id is None:
        return None
    return await session.scalar(
        select(User.full_name)
        .join(Faculty, Faculty.user_id == User.id)
        .where(Faculty.id == faculty_id)
    )


async def _editable(
    session: AsyncSession, principal: Principal, change_id: uuid.UUID
) -> ItemContext:
    """The department admin changes a draft or sent-back proposal."""
    ctx = await items.load_ctx(session, principal, KIND, change_id, lock=True)
    workflow.assert_editable(principal, ctx)  # its author, while a draft or sent back
    return ctx


@router.post("/scholars/{scholar_id}/supervisor-changes", response_model=ItemView, status_code=201)
async def propose(
    scholar_id: uuid.UUID,
    body: SupervisorChangeIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    await directory.require_admin_over_scholar(session, principal, scholar)
    if scholar.supervisor_id is None:
        raise ApiError(
            422, "no_supervisor_yet", "This scholar has no supervisor yet: assign one directly."
        )
    if body.to_faculty_id == scholar.supervisor_id:
        raise ApiError(422, "same_supervisor", "This is the scholar's supervisor already.")
    await directory.check_supervisor(session, scholar, body.to_faculty_id)
    change = await insert(
        session,
        principal,
        SupervisorChange(
            scholar_id=scholar.id,
            from_faculty_id=scholar.supervisor_id,
            from_name=await _name(session, scholar.supervisor_id),
            to_name=await _name(session, body.to_faculty_id),
            **body.model_dump(),
        ),
    )
    await session.commit()
    return await items.view(
        session, principal, await items.load_ctx(session, principal, KIND, change.id)
    )


@router.patch("/supervisor-changes/{change_id}", response_model=ItemView)
async def edit(
    change_id: uuid.UUID,
    body: SupervisorChangeUpdate,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await _editable(session, principal, change_id)
    changes = body.model_dump(exclude_unset=True)
    if "to_faculty_id" in changes:
        if changes["to_faculty_id"] == ctx.scholar.supervisor_id:
            raise ApiError(422, "same_supervisor", "This is the scholar's supervisor already.")
        await directory.check_supervisor(session, ctx.scholar, changes["to_faculty_id"])
        changes["to_name"] = await _name(session, changes["to_faculty_id"])
    await update(session, principal, ctx.item, changes)
    await session.commit()
    return await items.view(session, principal, ctx)


@router.delete("/supervisor-changes/{change_id}", status_code=204)
async def withdraw(
    change_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Withdraw a draft or sent-back proposal."""
    ctx = await _editable(session, principal, change_id)
    await soft_delete(session, principal, ctx.item)  # type: ignore[arg-type]
    await session.commit()
