"""What a six-monthly progress report holds (PRD F8): the sections of the template in force,
and the period's activity the system already knows. State stays with workflow.py."""

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.enums import DEFAULT_APR_SECTIONS
from app.errors import ApiError
from app.models import Conference, Meeting, ProgressReport, Publication, Scholar, Settings
from app.modules import module_enabled
from app.workflow import ItemContext, violation


def effective(settings: Settings) -> list[dict[str, Any]]:
    """The university's own sections while its toggle is on, else the standard ones."""
    return list(settings.apr_sections if settings.apr_custom_template else DEFAULT_APR_SECTIONS)


async def template(session: AsyncSession) -> list[dict[str, Any]]:
    settings = await session.get(Settings, 1)
    assert settings is not None, "settings row is seeded by migration 0001"
    return effective(settings)


async def clean_sections(
    session: AsyncSession, sections: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Keep what the scholar wrote, in template order; a heading the template lacks is refused."""
    names = [s["name"] for s in await template(session)]
    given = {s["name"]: s["text"] for s in sections}
    unknown = sorted(set(given) - set(names))
    if unknown:
        raise ApiError(
            422,
            "unknown_section",
            f"The report template has no section called {', '.join(unknown)}. Reload the page.",
        )
    return [{"name": n, "text": given[n]} for n in names if n in given]


async def require_complete(session: AsyncSession, _: Principal, ctx: ItemContext) -> None:
    """Submit gate: every section of today's template is written."""
    report: ProgressReport = ctx.item  # type: ignore[assignment]
    written = {s["name"] for s in report.sections if s["text"].strip()}
    missing = [s["name"] for s in await template(session) if s["name"] not in written]
    if missing:
        raise violation(f"Write these sections before submitting: {', '.join(missing)}.")


def period_dates(year: int, period: str) -> tuple[date, date]:
    if period == "January-June":
        return date(year, 1, 1), date(year, 6, 30)
    return date(year, 7, 1), date(year, 12, 31)


async def activity(session: AsyncSession, scholar: Scholar, year: int, period: str) -> dict:
    """Counts and titles only, all readable by anyone who reads the report (SECURITY.md §3):
    that a meeting happened is never redacted, and publications and conferences are read by
    every role that reads progress reports."""
    start, end = period_dates(year, period)
    meetings = await session.scalar(
        select(func.count())
        .select_from(Meeting)
        .where(
            Meeting.scholar_id == scholar.id,
            Meeting.deleted_at.is_(None),
            Meeting.meeting_date.between(start, end),
        )
    )
    publications = conferences = None
    if await module_enabled(session, "publications"):
        # ponytail: a publication carries a year, not a date, so both halves of a year list it.
        rows = await session.execute(
            select(Publication.title, Publication.pub_status)
            .where(
                Publication.scholar_id == scholar.id,
                Publication.deleted_at.is_(None),
                Publication.pub_year == year,
            )
            .order_by(Publication.title)
        )
        publications = [f"{title} ({status})" for title, status in rows]
    if await module_enabled(session, "conferences"):
        rows = await session.execute(
            select(Conference.event_name, Conference.event_date)
            .where(
                Conference.scholar_id == scholar.id,
                Conference.deleted_at.is_(None),
                Conference.event_date.between(start, end),
            )
            .order_by(Conference.event_date)
        )
        conferences = [f"{name} ({day:%d %b %Y})" for name, day in rows]
    return {"meetings": meetings or 0, "publications": publications, "conferences": conferences}
