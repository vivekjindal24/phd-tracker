"""Optional-module switch (PRD F4). Module routers declare require_module("<key>")."""

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.enums import ModuleKey
from app.errors import ApiError
from app.models import Module


async def module_enabled(session: AsyncSession, key: ModuleKey) -> bool:
    return bool(await session.scalar(select(Module.enabled).where(Module.key == key)))


def require_module(key: ModuleKey):
    async def guard(session: AsyncSession = Depends(get_session)) -> None:
        if not await module_enabled(session, key):
            raise ApiError(404, "module_disabled", "This feature is not enabled.")

    return guard
