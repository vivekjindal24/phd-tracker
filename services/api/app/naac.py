"""NAAC Criterion 3 research data (PRD M9): the underlying rows, one sheet each, built from
records already kept. Metric numbers and scores are not computed here: the framework changes,
the rows do not. Publications carry a calendar `pub_year`, so they are filtered on that year;
they are the scholars' and the faculty's both, each paper once."""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.enums import ModuleKey
from app.models import (
    Faculty,
    FacultyPublication,
    LedgerEntry,
    Milestone,
    OrgUnit,
    Patent,
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
    session: AsyncSession, period: Period, types: tuple[str, ...]
) -> list[tuple[Any, str, str]]:
    """Published papers of the years: scholars' approved through their chain and faculty's
    verified by the Library. A paper both recorded (one DOI) is one row naming each of them."""
    start, end = period
    years = (start.year, end.year)
    scholars = await session.execute(
        select(Publication, User.full_name, OrgUnit.name)
        .join(Scholar, Scholar.id == Publication.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .where(
            Publication.deleted_at.is_(None),
            Publication.state == "approved",
            Publication.pub_status == "published",
            Publication.pub_year.between(*years),
            Publication.pub_type.in_(types),
        )
    )
    faculty = await session.execute(
        select(FacultyPublication, User.full_name, OrgUnit.name)
        .join(Faculty, Faculty.id == FacultyPublication.faculty_id)
        .join(User, User.id == Faculty.user_id)
        .join(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .where(
            FacultyPublication.deleted_at.is_(None),
            FacultyPublication.verification == "verified",
            FacultyPublication.pub_status == "published",
            FacultyPublication.pub_year.between(*years),
            FacultyPublication.pub_type.in_(types),
        )
    )
    papers: dict[Any, tuple[Any, list[str], list[str]]] = {}
    for rows, who in ((scholars, "scholar"), (faculty, "faculty")):
        for p, name, unit in rows:
            _, names, units = papers.setdefault(p.doi.lower() if p.doi else p.id, (p, [], []))
            names.append(f"{name} ({who})")
            if unit not in units:
                units.append(unit)
    ordered = sorted(papers.values(), key=lambda e: (e[0].pub_year, e[0].title))
    return [(p, "; ".join(names), "; ".join(units)) for p, names, units in ordered]


async def _publications(session: AsyncSession, period: Period) -> Rows:
    rows = await _publication_rows(session, period, JOURNAL_TYPES)
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
    rows = await _publication_rows(session, period, ("book_chapter",))
    return [
        [p.pub_year, p.title, p.authors, p.venue, p.issn_isbn, p.doi, name, unit]
        for p, name, unit in rows
    ]


async def _patents(session: AsyncSession, period: Period) -> Rows:
    """Each verified patent published or granted in the years, a row per event (NAAC asks for
    patents published and awarded). One recorded by both a scholar and a member of faculty
    under the same application number is one row naming each."""
    start, end = period
    rows = await session.execute(
        select(Patent, User.full_name, OrgUnit.name)
        .outerjoin(Faculty, Faculty.id == Patent.faculty_id)
        .outerjoin(Scholar, Scholar.id == Patent.scholar_id)
        .join(User, User.id == func.coalesce(Faculty.user_id, Scholar.user_id))
        .join(OrgUnit, OrgUnit.id == func.coalesce(Faculty.unit_id, Scholar.unit_id))
        .where(
            Patent.deleted_at.is_(None),
            Patent.verification == "verified",
            or_(Patent.published_on.between(start, end), Patent.granted_on.between(start, end)),
        )
    )
    found: dict[str, tuple[Patent, list[str], list[str]]] = {}
    for p, name, unit in rows:
        key = "".join(p.application_number.split()).lower()
        _, names, units = found.setdefault(key, (p, [], []))
        names.append(f"{name} ({'faculty' if p.faculty_id else 'scholar'})")
        if unit not in units:
            units.append(unit)
    out: Rows = []
    for p, names, units in found.values():
        for event, day in (("Published", p.published_on), ("Granted", p.granted_on)):
            if day is not None and start <= day <= end:
                out.append(
                    [
                        academic_year(day),
                        event,
                        p.title,
                        p.inventors,
                        p.application_number,
                        p.patent_number,
                        p.office,
                        str(day),
                        "; ".join(names),
                        "; ".join(units),
                    ]
                )
    return sorted(out, key=lambda r: (r[7], r[2]))


# A sheet built from an optional module stops with it (SECURITY.md §3).
SHEET_MODULES: dict[str, ModuleKey] = {
    "projects": "projects",
    "publications": "publications",
    "books": "publications",
    "patents": "patents",
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
            "Recorded by",
            "Unit",
        ],
        _publications,
    ),
    "patents": (
        "Patents published and granted",
        [
            "Academic year",
            "Event",
            "Title",
            "Inventors",
            "Application number",
            "Patent number",
            "Patent office",
            "Date",
            "Recorded by",
            "Unit",
        ],
        _patents,
    ),
    "books": (
        "Books and chapters",
        ["Year", "Title", "Authors", "Publisher / venue", "ISBN", "DOI", "Recorded by", "Unit"],
        _books,
    ),
}
