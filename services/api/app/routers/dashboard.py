from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import dashboard
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """One section per role the caller holds (PRD F10); every number is scope-filtered."""
    return await dashboard.build(session, principal)
