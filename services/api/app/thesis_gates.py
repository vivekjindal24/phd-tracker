"""What a thesis must clear before it moves on (owner, 2026-11-22): the minimum time from
admission and the approved publications before the scholar submits; the plagiarism limit
before the Library approves. Each limit is a university setting; the gates block, they do not
warn. The scholar sees the same list on the thesis page before trying."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import dates, workflow
from app.auth.principal import Principal
from app.duration import add_years
from app.enums import LOCAL_TZ
from app.errors import ApiError
from app.models import Publication, Scholar, Settings, ThesisSubmission
from app.workflow import ItemContext

INDEXED = ("scopus", "wos", "ugc_care")


@dataclass(frozen=True)
class Gate:
    label: str
    met: bool
    detail: str


async def _settings(session: AsyncSession) -> Settings:
    row = await session.get(Settings, 1)
    assert row is not None, "settings row is seeded by migration 0001"
    return row


def _duration(scholar: Scholar, years: int) -> Gate:
    label = f"{years} years from admission"
    if scholar.admission_date is None:
        return Gate(label, False, "The admission date is not recorded; the department records it.")
    opens = add_years(scholar.admission_date, years)
    if opens <= datetime.now(LOCAL_TZ).date():
        return Gate(label, True, f"Admitted {dates.day(scholar.admission_date)}.")
    return Gate(label, False, f"The thesis can be submitted from {dates.day(opens)}.")


async def _publications(session: AsyncSession, scholar: Scholar, s: Settings) -> Gate:
    stmt = select(func.count()).where(
        Publication.scholar_id == scholar.id,
        Publication.state == "approved",
        Publication.pub_status.in_(("accepted", "published")),
        Publication.deleted_at.is_(None),
    )
    if s.publications_indexed_only:
        stmt = stmt.where(Publication.indexing.overlap(list(INDEXED)))
    have = await session.scalar(stmt) or 0
    which = " in Scopus, Web of Science or UGC-CARE" if s.publications_indexed_only else ""
    need = s.min_publications
    label = f"{need} approved publication{'s' if need > 1 else ''}{which}"
    return Gate(label, have >= need, f"{have} approved (accepted or published) so far.")


async def gates(session: AsyncSession, scholar: Scholar) -> list[Gate]:
    """The gates this university has switched on, and whether the scholar clears each."""
    s = await _settings(session)
    out = []
    if s.min_duration_years:
        out.append(_duration(scholar, s.min_duration_years))
    if s.min_publications:
        out.append(await _publications(session, scholar, s))
    return out


async def require_cleared(session: AsyncSession, scholar: Scholar) -> None:
    unmet = [f"{g.label}: {g.detail}" for g in await gates(session, scholar) if not g.met]
    if unmet:
        raise ApiError(409, "thesis_gate", "The thesis cannot be submitted yet. " + " ".join(unmet))


async def require_plagiarism_within_limit(
    session: AsyncSession, _: Principal, ctx: ItemContext
) -> None:
    """At the Library step: a score above the limit is sent back, never approved."""
    thesis: ThesisSubmission = ctx.item  # type: ignore[assignment]
    if workflow.current_kind(ctx) != "library" or thesis.plagiarism_score is None:
        return
    limit = (await _settings(session)).max_plagiarism_percent
    if thesis.plagiarism_score > limit:
        raise workflow.violation(
            f"The plagiarism score {thesis.plagiarism_score:g}% is above the university's limit "
            f"of {limit:g}%. Send the thesis back for revision."
        )
