"""NAAC Criterion 3 research data (PRD M9): the underlying rows, one sheet each, built from
records already kept. Metric numbers and scores are not computed here: the framework changes,
the rows do not. Publications carry a calendar `pub_year`, so they are filtered on that year."""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.enums import ModuleKey
from app.models import (
    Faculty,
    LedgerEntry,
    Milestone,
    OrgUnit,
    Project,
    Publication,
    Scholar,
    User,
)

AY_START_MONTH = 7  # Indian academic year: July to June
JOURNAL_TYPES = ("journal", "conference")

Rows = list[list[Any]]
Period = tuple[date, date]


def academic_year(day: date) -> str:
    start = day.year if day.month >= AY_START_MONTH else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def _yes(flag: bool) -> str:
    return "Yes" if flag else "No"


async def _projects(session: AsyncSession, period: Period) -> Rows:
    start, end = period
    grant = aliased(LedgerEntry)
    rows = await session.execute(
        select(Project, User.full_name, OrgUnit.name, grant)
        .join(Faculty, Faculty.id == Project.pi_id)
        .join(User, User.id == Faculty.user_id)
        .join(OrgUnit, OrgUnit.id == Project.unit_id)
        .outerjoin(
            grant,
            (grant.project_id == Project.id)
            & (grant.entry_kind == "disbursement")
            & grant.deleted_at.is_(None),
        )
        .where(Project.deleted_at.is_(None))
        .order_by(Project.start_date, Project.title, grant.entry_date)
    )
    out: Rows = []
    for project, pi, unit, entry in rows:
        day = entry.entry_date if entry else project.start_date
        if start <= day <= end:
            out.append(
                [
                    academic_year(day),
                    project.title,
                    pi,
                    unit,
                    project.agency,
                    project.sanction_number,
                    project.amount_sanctioned,
                    project.start_date.isoformat(),
                    project.end_date.isoformat(),
                    entry.entry_date.isoformat() if entry else None,
                    entry.reference if entry else None,
                    entry.amount if entry else None,
                ]
            )
    return out


async def _scholars(session: AsyncSession, period: Period) -> Rows:
    start, end = period
    guide = aliased(User)
    person = aliased(User)
    base = (
        select(Scholar, person.full_name, guide.full_name, Faculty.designation, OrgUnit.name)
        .join(person, person.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .outerjoin(Faculty, Faculty.id == Scholar.supervisor_id)
        .outerjoin(guide, guide.id == Faculty.user_id)
        .where(Scholar.deleted_at.is_(None))
    )
    registered = await session.execute(
        base.add_columns(Scholar.admission_date).where(Scholar.admission_date.between(start, end))
    )
    awarded = await session.execute(
        base.add_columns(Milestone.resolution_date)
        .join(Milestone, Milestone.scholar_id == Scholar.id)
        .where(
            Milestone.milestone_type == "degree_awarded",
            Milestone.status == "Approved",
            Milestone.deleted_at.is_(None),
            Milestone.resolution_date.between(start, end),
        )
    )
    rows = [("Registered", *r) for r in registered] + [("Awarded", *r) for r in awarded]
    rows.sort(key=lambda r: (r[3] or "", r[6], r[2]))
    return [
        [academic_year(day), event, guide_name, designation, name, s.roll_number, unit, str(day)]
        for event, s, name, guide_name, designation, unit, day in rows
    ]


async def _publication_rows(
    session: AsyncSession, period: Period, *conditions: Any
) -> list[tuple[Publication, str, str]]:
    start, end = period
    rows = await session.execute(
        select(Publication, User.full_name, OrgUnit.name)
        .join(Scholar, Scholar.id == Publication.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .where(
            Publication.deleted_at.is_(None),
            Publication.state == "approved",
            Publication.pub_status == "published",
            Publication.pub_year.between(start.year, end.year),
            *conditions,
        )
        .order_by(Publication.pub_year, Publication.title)
    )
    return [tuple(r) for r in rows]


async def _publications(session: AsyncSession, period: Period) -> Rows:
    rows = await _publication_rows(session, period, Publication.pub_type.in_(JOURNAL_TYPES))
    return [
        [
            p.pub_year,
            p.title,
            p.authors,
            p.pub_type,
            p.venue,
            p.issn_isbn,
            p.doi,
            _yes("ugc_care" in p.indexing),
            _yes("scopus" in p.indexing),
            _yes("wos" in p.indexing),
            name,
            unit,
        ]
        for p, name, unit in rows
    ]


async def _books(session: AsyncSession, period: Period) -> Rows:
    rows = await _publication_rows(session, period, Publication.pub_type == "book_chapter")
    return [
        [p.pub_year, p.title, p.authors, p.venue, p.issn_isbn, p.doi, name, unit]
        for p, name, unit in rows
    ]


# A sheet built from an optional module stops with it (SECURITY.md §3).
SHEET_MODULES: dict[str, ModuleKey] = {
    "projects": "projects",
    "publications": "publications",
    "books": "publications",
}

SHEETS: dict[str, tuple[str, list[str], Callable[[AsyncSession, Period], Awaitable[Rows]]]] = {
    "projects": (
        "Funded projects and grants received",
        [
            "Academic year",
            "Project",
            "Principal investigator",
            "Unit",
            "Funding agency",
            "Sanction number",
            "Amount sanctioned",
            "Start date",
            "End date",
            "Grant received on",
            "Grant reference",
            "Grant received",
        ],
        _projects,
    ),
    "scholars": (
        "PhD scholars registered and awarded per guide",
        [
            "Academic year",
            "Event",
            "Guide",
            "Guide designation",
            "Scholar",
            "Roll number",
            "Unit",
            "Date",
        ],
        _scholars,
    ),
    "publications": (
        "Publications with indexing",
        [
            "Year",
            "Title",
            "Authors",
            "Type",
            "Venue",
            "ISSN / ISBN",
            "DOI",
            "UGC-CARE",
            "Scopus",
            "Web of Science",
            "Scholar",
            "Unit",
        ],
        _publications,
    ),
    "books": (
        "Books and chapters",
        ["Year", "Title", "Authors", "Publisher / venue", "ISBN", "DOI", "Scholar", "Unit"],
        _books,
    ),
}
