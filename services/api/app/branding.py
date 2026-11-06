"""Per-install branding: the university's name (the root org unit), address and logo. Co-branded
by design: the university leads, Anveshan stays in the footer and the product name. Public on
purpose, because the login page shows it before anyone signs in; nothing private lives here."""

import base64
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.crud import insert, soft_delete
from app.errors import ApiError
from app.models import OrgUnit, Settings, UniversityLogo

MAX_LOGO_BYTES = 500_000
MAGIC_TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
TOO_LARGE = ApiError(413, "logo_too_large", "The logo can be at most 500 KB.")
INVALID = ApiError(422, "invalid_logo", "Upload the logo as a PNG or JPEG image.")


async def _name(session: AsyncSession) -> str:
    return (
        await session.scalar(
            select(OrgUnit.name).where(OrgUnit.parent_id.is_(None), OrgUnit.deleted_at.is_(None))
        )
        or "University"
    )


async def _address(session: AsyncSession) -> str:
    return await session.scalar(select(Settings.university_address)) or ""


async def current_logo(session: AsyncSession) -> UniversityLogo | None:
    return await session.scalar(
        select(UniversityLogo)
        .where(UniversityLogo.deleted_at.is_(None))
        .order_by(UniversityLogo.created_at.desc())
        .limit(1)
    )


async def public_view(session: AsyncSession) -> dict[str, Any]:
    logo = await current_logo(session)
    return {
        "university": await _name(session),
        "address": await _address(session),
        "has_logo": logo is not None,
        "logo_version": logo.created_at.timestamp() if logo else None,
    }


async def export_fields(session: AsyncSession) -> dict[str, Any]:
    logo = await current_logo(session)
    return {
        "university": await _name(session),
        "address": await _address(session),
        "logo": base64.b64encode(logo.content).decode() if logo else None,
    }


async def read_logo_upload(request: Request) -> tuple[bytes, str]:
    """The raw request body, refused once past the cap. The type comes from the bytes: the
    Content-Type header is the sender's claim, and SVG (which can carry script) never passes."""
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_LOGO_BYTES:
            raise TOO_LARGE
        chunks.append(chunk)
    content = b"".join(chunks)
    for magic, content_type in MAGIC_TYPES.items():
        if content.startswith(magic):
            return content, content_type
    raise INVALID


async def replace_logo(
    session: AsyncSession, principal: Principal, content: bytes, content_type: str
) -> None:
    await remove_logo(session, principal)
    await insert(session, principal, UniversityLogo(content=content, content_type=content_type))


async def remove_logo(session: AsyncSession, principal: Principal) -> None:
    if logo := await current_logo(session):
        await soft_delete(session, principal, logo)
