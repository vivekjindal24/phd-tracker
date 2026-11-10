"""Research ethics clearance per scholar (PRD F9c): what is recorded, and the thesis gate."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError
from app.models import EthicsClearance, Settings


async def records(session: AsyncSession, scholar_id: uuid.UUID) -> list[EthicsClearance]:
    rows = await session.scalars(
        select(EthicsClearance)
        .where(EthicsClearance.scholar_id == scholar_id, EthicsClearance.deleted_at.is_(None))
        .order_by(EthicsClearance.approved_on.desc().nulls_last(), EthicsClearance.created_at)
    )
    return list(rows)


async def required(session: AsyncSession) -> bool:
    settings = await session.get(Settings, 1)
    assert settings is not None, "settings row is seeded by migration 0001"
    return settings.require_ethics


async def require_recorded(session: AsyncSession, scholar_id: uuid.UUID) -> None:
    """The thesis gate: any record counts, a clearance or a recorded 'not required'. A lapsed
    clearance still counts — it covered the work when the work was done."""
    if await required(session) and not await records(session, scholar_id):
        raise ApiError(
            409,
            "ethics_pending",
            "Your ethics clearance is not recorded yet. Ask your department or the Research "
            "Office to record it, or that none is required, before submitting the thesis.",
        )
