"""Specimen signatures (PRD F17b, signatures.py): a person's own, and the keepers' work list."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import branding, signatures
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.errors import forbidden
from app.schemas import PendingSignatureOut, SignatureOut

router = APIRouter(tags=["people"])


@router.get("/users/{user_id}/signature", response_model=SignatureOut | None)
async def get_signature(
    user_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict | None:
    await signatures.require_self_or_keeper(session, principal, user_id)
    return signatures.view(await signatures.current(session, user_id))


@router.put("/users/{user_id}/signature", status_code=204)
async def put_signature(
    user_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await signatures.require_self_or_keeper(session, principal, user_id)
    content, content_type = await branding.read_image_upload(request, "signature")
    await signatures.replace(session, principal, user_id, content, content_type)
    await session.commit()


@router.post("/users/{user_id}/signature/confirm", status_code=204)
async def confirm_signature(
    user_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await signatures.confirm(session, principal, user_id)
    await session.commit()


@router.delete("/users/{user_id}/signature", status_code=204)
async def delete_signature(
    user_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await signatures.require_self_or_keeper(session, principal, user_id)
    await signatures.remove(session, principal, user_id)
    await session.commit()


@router.get("/signatures/pending", response_model=list[PendingSignatureOut])
async def pending_signatures(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    keeps = principal.is_root_admin or "research_office" in principal.office_roles
    if not (keeps or principal.unit_paths("admin")):
        raise forbidden()
    return await signatures.pending(session, principal)
