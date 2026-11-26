"""Scholar photos (PRD F6, photos.py)."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import branding, photos
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.errors import forbidden
from app.schemas import PhotoOut

router = APIRouter(prefix="/scholars/{scholar_id}/photo", tags=["directory"])


@router.get("", response_model=PhotoOut)
async def get_photo(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    scholar = await photos.visible_scholar(session, principal, scholar_id)
    return photos.view(
        await photos.current(session, scholar_id),
        await photos.may_change(session, principal, scholar),
    )


async def _changer(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> None:
    scholar = await photos.visible_scholar(session, principal, scholar_id)
    if not await photos.may_change(session, principal, scholar):
        raise forbidden()


@router.put("", status_code=204)
async def put_photo(
    scholar_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _changer(session, principal, scholar_id)
    content, content_type = await branding.read_image_upload(request, "photo")
    await photos.replace(session, principal, scholar_id, content, content_type)
    await session.commit()


@router.delete("", status_code=204)
async def delete_photo(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _changer(session, principal, scholar_id)
    await photos.remove(session, principal, scholar_id)
    await session.commit()
