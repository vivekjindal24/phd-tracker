"""Viva arrangements (PRD M3, Forms X and XI): the Exam Office proposes the date, place and board;
the arrangement then moves up its approval chain through /items like any other item, and once
approved the external examiners are emailed. The viva itself is recorded on the thesis."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, thesis, viva, workflow
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import Faculty, VivaArrangement, VivaBoardMember
from app.rbac import require_perm
from app.schemas import ItemView
from app.schemas.research import (
    BoardMemberIn,
    BoardView,
    InviteOut,
    VivaArrangementIn,
    VivaArrangementUpdate,
)
from app.workflow import ItemContext

router = APIRouter(tags=["vivas"])
ENTITY = "viva_arrangements"
KIND = "viva_arrangement"


async def _ctx(
    session: AsyncSession, principal: Principal, arrangement_id: uuid.UUID, *, lock: bool = False
) -> ItemContext:
    return await items.load_ctx(session, principal, KIND, arrangement_id, lock=lock)


async def _editable(
    session: AsyncSession, principal: Principal, arrangement_id: uuid.UUID
) -> ItemContext:
    """The Exam Office changes a draft or sent-back arrangement, never for its own scholar."""
    ctx = await _ctx(session, principal, arrangement_id, lock=True)
    thesis.require_not_guide(principal, ctx)
    workflow.assert_editable(principal, ctx)
    return ctx


@router.post("/theses/{thesis_id}/viva-arrangements", response_model=ItemView, status_code=201)
async def arrange_viva(
    thesis_id: uuid.UUID,
    body: VivaArrangementIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await thesis.load_thesis(session, principal, thesis_id, lock=True)
    thesis.require_approved(ctx)
    thesis.require_not_guide(principal, ctx)
    if await viva.open_arrangement(session, thesis_id) is not None:
        raise ApiError(
            409,
            "viva_already_arranged",
            "This thesis already has a viva arranged; record that viva or withdraw it first.",
        )
    arrangement = await insert(
        session,
        principal,
        VivaArrangement(scholar_id=ctx.scholar.id, thesis_id=thesis_id, **body.model_dump()),
    )
    await session.commit()
    return await items.view(session, principal, await _ctx(session, principal, arrangement.id))


@router.patch("/viva-arrangements/{arrangement_id}", response_model=ItemView)
async def change_arrangement(
    arrangement_id: uuid.UUID,
    body: VivaArrangementUpdate,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await _editable(session, principal, arrangement_id)
    await update(session, principal, ctx.item, body.model_dump(exclude_unset=True))
    await session.commit()
    return await items.view(session, principal, ctx)


@router.delete("/viva-arrangements/{arrangement_id}", status_code=204)
async def withdraw_arrangement(
    arrangement_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Withdraw a draft or sent-back arrangement, with its board."""
    ctx = await _editable(session, principal, arrangement_id)
    for member in await viva.members(session, ctx.item.id):
        await soft_delete(session, principal, member)
    await soft_delete(session, principal, ctx.item)  # type: ignore[arg-type]
    await session.commit()


@router.get("/viva-arrangements/{arrangement_id}/board", response_model=BoardView)
async def get_board(
    arrangement_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await viva.board(session, principal, await _ctx(session, principal, arrangement_id))


@router.post("/viva-arrangements/{arrangement_id}/board", response_model=BoardView)
async def add_board_member(
    arrangement_id: uuid.UUID,
    body: BoardMemberIn,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await _editable(session, principal, arrangement_id)
    if body.faculty_id is not None:
        if body.faculty_id == ctx.scholar.supervisor_id:
            raise ApiError(409, "supervisor_on_board", "The supervisor is on the board already.")
        known = await session.scalar(
            select(Faculty.id).where(Faculty.id == body.faculty_id, Faculty.deleted_at.is_(None))
        )
        if known is None:
            raise ApiError(422, "faculty_not_found", "This faculty member does not exist.")
    await insert(
        session, principal, VivaBoardMember(arrangement_id=ctx.item.id, **body.model_dump())
    )
    await session.commit()
    return await viva.board(session, principal, ctx)


@router.delete("/viva-board-members/{member_id}", response_model=BoardView)
async def remove_board_member(
    member_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    member = await session.scalar(
        select(VivaBoardMember).where(
            VivaBoardMember.id == member_id, VivaBoardMember.deleted_at.is_(None)
        )
    )
    if member is None:
        raise forbidden()
    ctx = await _editable(session, principal, member.arrangement_id)
    await soft_delete(session, principal, member)
    await session.commit()
    return await viva.board(session, principal, ctx)


@router.post("/viva-arrangements/{arrangement_id}/invite", response_model=InviteOut)
async def invite_examiners(
    arrangement_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Email the external examiners the approved arrangement; may be sent again."""
    ctx = await _ctx(session, principal, arrangement_id, lock=True)
    if not (await viva.board(session, principal, ctx))["can_invite"]:
        raise ApiError(
            422,
            "cannot_invite",
            "Invitations go out once the arrangement is approved, before its viva is recorded.",
        )
    sent = await viva.invite(session, ctx)
    now = datetime.now(UTC)
    await update(session, principal, ctx.item, {"invited_at": now})
    await session.commit()
    return {"sent": sent, "invited_at": now}
