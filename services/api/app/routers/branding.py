"""Public branding: what the login page and the top bar show (branding.py)."""

from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import branding
from app.db import get_session
from app.errors import ApiError

router = APIRouter(prefix="/branding", tags=["branding"])


@router.get("")
async def get_branding(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    return await branding.public_view(session)


@router.get("/logo")
async def get_logo(session: AsyncSession = Depends(get_session)) -> Response:
    logo = await branding.current_logo(session)
    if logo is None:
        raise ApiError(404, "not_found", "No logo has been set.")
    return Response(
        logo.content,
        media_type=logo.content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
            "Cache-Control": "public, max-age=3600",
        },
    )
