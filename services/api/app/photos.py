"""Scholar photos (PRD F6): whoever may open a scholar's profile sees the photo; the scholar
or an admin over their unit puts it there or takes it away. The image travels inline as a
data: URL, as specimen signatures do."""

import base64
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete
from app.errors import forbidden
from app.models import Scholar, ScholarPhoto


async def visible_scholar(
    session: AsyncSession, principal: Principal, scholar_id: uuid.UUID
) -> Scholar:
    """The scholar, if the caller may open their profile (the directory's own rule)."""
    scholar = await session.scalar(
        select(Scholar).where(
            Scholar.id == scholar_id,
            Scholar.deleted_at.is_(None),
            scope.scholar_directory_predicate(principal),
        )
    )
    if scholar is None:
        raise forbidden()
    return scholar


async def may_change(session: AsyncSession, principal: Principal, scholar: Scholar) -> bool:
    if principal.scholar_id == scholar.id:
        return True
    return principal.covers("admin", await scope.unit_path(session, scholar.unit_id))


async def current(session: AsyncSession, scholar_id: uuid.UUID) -> ScholarPhoto | None:
    return await session.scalar(
        select(ScholarPhoto).where(
            ScholarPhoto.scholar_id == scholar_id, ScholarPhoto.deleted_at.is_(None)
        )
    )


def view(photo: ScholarPhoto | None, can_change: bool) -> dict[str, Any]:
    image = None
    if photo is not None:
        image = f"data:{photo.content_type};base64,{base64.b64encode(photo.content).decode()}"
    return {"image": image, "can_change": can_change}


async def remove(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> None:
    if photo := await current(session, scholar_id):
        await soft_delete(session, principal, photo)


async def replace(
    session: AsyncSession,
    principal: Principal,
    scholar_id: uuid.UUID,
    content: bytes,
    content_type: str,
) -> None:
    await remove(session, principal, scholar_id)
    await insert(
        session,
        principal,
        ScholarPhoto(scholar_id=scholar_id, content=content, content_type=content_type),
    )
