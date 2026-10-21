import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.errors import forbidden
from app.models import Notification
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    before: datetime | None = None,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == principal.user_id)
    if before is not None:
        stmt = stmt.where(Notification.created_at < before)
    rows = await session.scalars(stmt.order_by(Notification.created_at.desc()).limit(limit))
    return list(rows)


@router.post("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await session.get(Notification, notification_id)
    if row is None or row.user_id != principal.user_id:
        raise forbidden()
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await session.commit()


@router.post("/read-all", status_code=204)
async def mark_all_read(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == principal.user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    await session.commit()
