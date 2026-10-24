"""Generic approvable-item endpoints: view, act, queue (PRD F3, UX Flows 1-2)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, workflow
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.enums import ItemType
from app.schemas import ApproveIn, ItemView, QueueEntry, SendBackIn

router = APIRouter(tags=["items"])


async def _act_and_view(session, principal, item_type, item_id, action) -> dict[str, Any]:
    ctx = await items.load_ctx(session, principal, item_type, item_id, lock=True)
    await action(ctx)
    await session.commit()
    return await items.view(session, principal, ctx)


@router.get("/items/{item_type}/{item_id}", response_model=ItemView)
async def get_item(
    item_type: ItemType,
    item_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await items.load_ctx(session, principal, item_type, item_id)
    return await items.view(session, principal, ctx)


@router.post("/items/{item_type}/{item_id}/submit", response_model=ItemView)
async def submit(
    item_type: ItemType,
    item_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _act_and_view(
        session, principal, item_type, item_id, lambda ctx: items.submit(session, principal, ctx)
    )


@router.post("/items/{item_type}/{item_id}/resubmit", response_model=ItemView)
async def resubmit(
    item_type: ItemType,
    item_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _act_and_view(
        session,
        principal,
        item_type,
        item_id,
        lambda ctx: items.resubmit(session, principal, ctx),
    )


@router.post("/items/{item_type}/{item_id}/approve", response_model=ItemView)
async def approve(
    item_type: ItemType,
    item_id: uuid.UUID,
    body: ApproveIn | None = None,  # the comment is optional, so is the body
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _act_and_view(
        session,
        principal,
        item_type,
        item_id,
        lambda ctx: items.approve(session, principal, ctx, body.comment if body else None),
    )


@router.post("/items/{item_type}/{item_id}/send-back", response_model=ItemView)
async def send_back(
    item_type: ItemType,
    item_id: uuid.UUID,
    body: SendBackIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _act_and_view(
        session,
        principal,
        item_type,
        item_id,
        lambda ctx: workflow.send_back(session, principal, ctx, body.comment, body.to_step),
    )


@router.get("/queue", response_model=list[QueueEntry])
async def queue(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    return await items.queue(session, principal)
