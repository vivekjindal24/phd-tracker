"""In-app notifications, written in the same transaction as the event that causes them
(ARCHITECTURE.md §6). Email delivery is added once SMTP is configured."""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


def notify(
    session: AsyncSession,
    user_ids: Iterable[uuid.UUID],
    category: str,
    title: str,
    body: str = "",
    link: str | None = None,
) -> None:
    for user_id in dict.fromkeys(user_ids):  # de-duplicate, keep order
        session.add(
            Notification(user_id=user_id, category=category, title=title, body=body, link=link)
        )


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return count or 0
