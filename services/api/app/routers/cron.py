"""The daily job (ARCHITECTURE.md §10): one call a day from the scheduler, authenticated by the
X-Cron-Secret header, idempotent per day through job_runs. Off when CRON_SECRET is unset."""

import hmac
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.errors import ApiError
from app.models import Faculty, Fellowship, JobRun, Scholar
from app.modules import module_enabled
from app.notify import notify

router = APIRouter(prefix="/internal/cron", tags=["internal"])
FELLOWSHIP_NOTICE_DAYS = 60  # PRD F5: "fellowship ending in 60 days"


async def _fellowships_ending(session: AsyncSession, today: date) -> int:
    # ponytail: exact-day match, so a day the scheduler misses sends no reminder for
    # fellowships ending that day; track reminded rows if the scheduler proves unreliable.
    if not await module_enabled(session, "fellowships"):
        return 0
    ends = today + timedelta(days=FELLOWSHIP_NOTICE_DAYS)
    rows = await session.execute(
        select(Scholar.user_id, Faculty.user_id)
        .join(Fellowship, Fellowship.scholar_id == Scholar.id)
        .outerjoin(Faculty, Faculty.id == Scholar.supervisor_id)
        .where(
            Fellowship.deleted_at.is_(None),
            Fellowship.status == "active",
            Fellowship.end_date == ends,
            Scholar.deleted_at.is_(None),
            Scholar.left_on.is_(None),
        )
    )
    count = 0
    for scholar_user, supervisor_user in rows:
        notify(
            session,
            [u for u in (scholar_user, supervisor_user) if u],
            "fellowship_ending",
            f"Fellowship ends on {ends:%d %b %Y}",
            f"The fellowship ends in {FELLOWSHIP_NOTICE_DAYS} days. Speak to the research "
            "office about an extension or the next step.",
            "/fellowships",
        )
        count += 1
    return count


@router.post("/daily")
async def daily(
    x_cron_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    if settings.cron_secret is None:
        raise ApiError(404, "not_configured", "The daily job is not configured on this server.")
    if x_cron_secret is None or not hmac.compare_digest(
        x_cron_secret.encode(), settings.cron_secret.encode()
    ):
        raise ApiError(401, "unauthorized", "Wrong or missing cron secret.")
    today = datetime.now(UTC).date()
    claimed = await session.scalar(
        insert(JobRun)
        .values(job_name="daily", run_date=today)
        .on_conflict_do_nothing(constraint="uq_job_runs")
        .returning(JobRun.id)
    )
    if claimed is None:
        return {"ran": False, "reason": "already ran today"}
    reminders = await _fellowships_ending(session, today)
    await session.commit()
    return {"ran": True, "fellowship_reminders": reminders}
