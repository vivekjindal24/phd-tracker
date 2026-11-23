"""The research-degree tables of the yearly government returns (PRD M9): NIRF's Ph.D. student
details, sponsored research and patents, and AISHE's Ph.D. enrolment, foreign students and
examination results. Counted from records already kept; each sheet is for one academic year
`year` (July `year` to June `year + 1`), NIRF's going back three years as its form does.

Whom a count leaves out is shown, not dropped: a scholar with no admission date gets a row of its
own, and one whose category or gender is not recorded a column of their own."""

from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import naac
from app.enums import ModuleKey
from app.models import LedgerEntry, Milestone, OrgUnit, Project, Scholar

Rows = list[list[Any]]
NIRF_YEARS = 3
FY_START_MONTH = 4  # India's financial year: April to March

# AISHE's columns: each category by gender; EWS is counted "out of General" (inside it too).
CATEGORY_COLUMNS = (
    ("General", ("general", "ews")),
    ("EWS (out of General)", ("ews",)),
    ("SC", ("sc",)),
    ("ST", ("st",)),
    ("OBC", ("obc",)),
)
GENDER_COLUMNS = (("Male", "male"), ("Female", "female"), ("Transgender", "transgender"))
SPLIT_HEADERS = [f"{c} {g}" for c, _ in CATEGORY_COLUMNS for g, _ in GENDER_COLUMNS]
NOT_PLACED = "Category or gender not recorded"
OTHER_MINORITIES = ("christian", "sikh", "buddhist", "jain", "parsi")
FOREIGN = (("NRI", "nri"), ("PIO", "pio"), ("Other foreign national", "foreign"))


def ay_bounds(year: int) -> tuple[date, date]:
    return date(year, naac.AY_START_MONTH, 1), date(year + 1, naac.AY_START_MONTH - 1, 30)


@dataclass(frozen=True)
class Placed:
    """A scholar with the dates the returns count by and the unit columns AISHE asks for."""

    s: Scholar
    viva: date | None
    awarded: date | None
    school: str
    department: str
    discipline: str

    def on_roll(self, start: date, end: date) -> bool:
        """On the rolls at some time in the year: admitted by its end, not gone before it began."""
        admitted = self.s.admission_date
        return (
            admitted is not None
            and admitted <= end
            and (self.s.left_on is None or self.s.left_on >= start)
            and (self.awarded is None or self.awarded >= start)
        )

    def pursuing_at(self, day: date) -> bool:
        """Still pursuing the degree on `day`: admitted, not awarded and not gone by then."""
        admitted = self.s.admission_date
        return (
            admitted is not None
            and admitted <= day
            and (self.s.left_on is None or self.s.left_on > day)
            and (self.awarded is None or self.awarded > day)
        )


async def _scholars(session: AsyncSession) -> list[Placed]:
    units = {u.id: u for u in await session.scalars(select(OrgUnit))}
    dates: dict[tuple[Any, str], date] = {
        (sid, kind): day
        for sid, kind, day in await session.execute(
            select(
                Milestone.scholar_id, Milestone.milestone_type, func.min(Milestone.resolution_date)
            )
            .where(
                Milestone.milestone_type.in_(("viva", "degree_awarded")),
                Milestone.status == "Approved",
                Milestone.deleted_at.is_(None),
            )
            .group_by(Milestone.scholar_id, Milestone.milestone_type)
        )
    }
    out = []
    for s in await session.scalars(select(Scholar).where(Scholar.deleted_at.is_(None))):
        unit = units[s.unit_id]
        parent = units.get(unit.parent_id) if unit.parent_id else None
        school = parent.name if parent and parent.parent_id else ""  # not the university itself
        out.append(
            Placed(
                s,
                dates.get((s.id, "viva")),
                dates.get((s.id, "degree_awarded")),
                school,
                unit.name,
                unit.aishe_discipline or "",
            )
        )
    return sorted(out, key=lambda p: (p.school, p.department))


def _split(people: Iterable[Placed]) -> list[int]:
    """AISHE's category-by-gender counts, the total, and those it cannot place."""
    counts: Counter[tuple[str, str]] = Counter()
    total = unplaced = 0
    for p in people:
        total += 1
        if p.s.category is None or p.s.gender is None:
            unplaced += 1
        counts[p.s.category or "", p.s.gender or ""] += 1
    cells = [
        sum(counts[c, g] for c in cats) for _, cats in CATEGORY_COLUMNS for _, g in GENDER_COLUMNS
    ]
    return [*cells, total, unplaced]


def _breakup(label: str, people: list[Placed]) -> Rows:
    """Total, PwBD, Muslim minority and other minorities (out of the total), as AISHE's blocks
    run; each other community's own row only when it has someone."""
    rows = [
        [f"{label}Total", *_split(people)],
        [f"{label}PwBD (out of total)", *_split(p for p in people if p.s.has_disability)],
        [
            f"{label}Muslim minority (out of total)",
            *_split(p for p in people if p.s.minority == "muslim"),
        ],
        [
            f"{label}Other minority (out of total)",
            *_split(p for p in people if p.s.minority in OTHER_MINORITIES),
        ],
    ]
    for community in OTHER_MINORITIES:
        mine = [p for p in people if p.s.minority == community]
        if mine:
            rows.append([f"{label}  of which {community.capitalize()}", *_split(mine)])
    return rows


def _no_admission(people: list[Placed]) -> Rows:
    missing = sum(1 for p in people if p.s.admission_date is None)
    note = f"Not counted: {missing} scholar(s) with no admission date recorded"
    return [[note]] if missing else []


def _by_unit(people: Iterable[Placed]) -> dict[tuple[str, str, str], list[Placed]]:
    groups: dict[tuple[str, str, str], list[Placed]] = defaultdict(list)
    for p in people:
        groups[p.school, p.department, p.discipline].append(p)
    return groups


# --- NIRF --------------------------------------------------------------------------------------


async def _nirf_phd(session: AsyncSession, year: int) -> Rows:
    people = await _scholars(session)

    def modes(group: Iterable[Placed]) -> list[int]:
        seen = Counter(p.s.study_mode for p in group)
        return [seen["full_time"], seen["part_time"], seen[None]]

    end = ay_bounds(year)[1]
    rows: Rows = [
        [
            f"Pursuing the doctoral programme till {naac.academic_year(end)} (on {end})",
            *modes(p for p in people if p.pursuing_at(end)),
        ]
    ]
    for y in range(year, year - NIRF_YEARS, -1):
        start, last = ay_bounds(y)
        graduated = (p for p in people if p.awarded and start <= p.awarded <= last)
        rows.append([f"Graduated in {naac.academic_year(start)}", *modes(graduated)])
    return rows + _no_admission(people)


async def _nirf_sponsored(session: AsyncSession, year: int) -> Rows:
    """Each financial year: the projects that received money in it, their agencies, and the
    amount received (the grant entries of the ledger)."""
    rows: Rows = []
    for y in range(year, year - NIRF_YEARS, -1):
        start, end = date(y, FY_START_MONTH, 1), date(y + 1, FY_START_MONTH - 1, 31)
        grants = (
            await session.execute(
                select(Project.id, Project.agency, LedgerEntry.amount)
                .join(LedgerEntry, LedgerEntry.project_id == Project.id)
                .where(
                    Project.deleted_at.is_(None),
                    LedgerEntry.deleted_at.is_(None),
                    LedgerEntry.entry_kind == "disbursement",
                    LedgerEntry.entry_date.between(start, end),
                )
            )
        ).all()
        received = round(sum(amount for _, _, amount in grants))
        rows.append(
            [
                f"{y}-{(y + 1) % 100:02d}",
                len({pid for pid, _, _ in grants}),
                len({" ".join(agency.lower().split()) for _, agency, _ in grants}),
                received,
                rupees_in_words(received),
            ]
        )
    return rows


async def _nirf_patents(session: AsyncSession, year: int) -> Rows:
    """Each calendar year: verified patents published and granted, each once (naac.py)."""
    rows: Rows = []
    for y in range(year, year - NIRF_YEARS, -1):
        found = await naac.patent_rows(session, (date(y, 1, 1), date(y, 12, 31)))
        events = Counter(event for _, event, *_ in found)
        rows.append([y, events["Published"], events["Granted"]])
    return rows


# --- AISHE -------------------------------------------------------------------------------------


async def _aishe_enrolment(session: AsyncSession, year: int) -> Rows:
    people = await _scholars(session)
    start, end = ay_bounds(year)
    rows: Rows = []
    for unit, group in _by_unit(p for p in people if p.on_roll(start, end)).items():
        by_year: dict[int, list[Placed]] = defaultdict(list)
        for p in group:
            assert p.s.admission_date is not None  # on_roll requires it
            admitted = int(naac.academic_year(p.s.admission_date)[:4])
            by_year[max(1, year - admitted + 1)].append(p)
        for study_year in sorted(by_year):
            rows += [[*unit, study_year, *r] for r in _breakup("", by_year[study_year])]
    return rows + _no_admission(people)


async def _aishe_foreign(session: AsyncSession, year: int) -> Rows:
    start, end = ay_bounds(year)
    abroad = [
        p
        for p in await _scholars(session)
        if p.on_roll(start, end) and p.s.nationality not in (None, "indian")
    ]
    groups: dict[tuple[str, str, str, str], list[Placed]] = defaultdict(list)
    for p in abroad:
        assert p.s.country is not None  # ck_scholars_country
        groups[p.school, p.department, p.discipline, p.s.country.strip()].append(p)

    def mf(people: list[Placed]) -> list[int]:
        genders = Counter(p.s.gender for p in people)
        return [genders["male"], genders["female"], len(people)]

    return [
        [
            *key,
            *[n for _, kind in FOREIGN for n in mf([p for p in group if p.s.nationality == kind])],
            *mf(group),
        ]
        for key, group in sorted(groups.items())
    ]


async def _aishe_results(session: AsyncSession, year: int) -> Rows:
    """Appeared: the viva voce (the final examination) was held in the year; awarded: the
    degree was awarded in it."""
    start, end = ay_bounds(year)
    people = await _scholars(session)
    rows: Rows = []
    for unit, group in _by_unit(people).items():
        appeared = [p for p in group if p.viva and start <= p.viva <= end]
        awarded = [p for p in group if p.awarded and start <= p.awarded <= end]
        if appeared or awarded:
            rows += [[*unit, *r] for r in _breakup("Appeared: ", appeared)]
            rows += [[*unit, *r] for r in _breakup("Awarded: ", awarded)]
    return rows


UNIT_COLUMNS = ["Faculty / school", "Department", "AISHE discipline"]
AISHE_SPLIT = [*SPLIT_HEADERS, "Total", NOT_PLACED]
Builder = Callable[[AsyncSession, int], Awaitable[Rows]]
SHEETS: dict[str, tuple[str, list[str], Builder]] = {
    "nirf-phd": (
        "NIRF: Ph.D. student details",
        ["", "Full time", "Part time", "Mode not recorded"],
        _nirf_phd,
    ),
    "nirf-sponsored": (
        "NIRF: sponsored research details",
        [
            "Financial year",
            "Total no. of sponsored projects",
            "Total no. of funding agencies",
            "Total amount received (Rs.)",
            "Amount received in words",
        ],
        _nirf_sponsored,
    ),
    "nirf-patents": (
        "NIRF: patents (IPR)",
        ["Calendar year", "No. of patents published", "No. of patents granted"],
        _nirf_patents,
    ),
    "aishe-enrolment": (
        "AISHE: Ph.D. student enrolment",
        [*UNIT_COLUMNS, "Year of study", "Row", *AISHE_SPLIT],
        _aishe_enrolment,
    ),
    "aishe-foreign": (
        "AISHE: Ph.D. foreign students",
        [
            *UNIT_COLUMNS,
            "Country",
            *[f"{label} {g}" for label, _ in FOREIGN for g in ("male", "female", "total")],
            "Total male",
            "Total female",
            "Total",
        ],
        _aishe_foreign,
    ),
    "aishe-results": (
        "AISHE: Ph.D. examination results",
        [*UNIT_COLUMNS, "Row", *AISHE_SPLIT],
        _aishe_results,
    ),
}
# A sheet built from an optional module stops with it (SECURITY.md §3).
SHEET_MODULES: dict[str, ModuleKey] = {"nirf-sponsored": "projects", "nirf-patents": "patents"}


# --- rupees in words (NIRF asks for the amount in words too) ------------------------------------

_ONES = [
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = ["_", "_", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return f"{_TENS[tens]} {_ONES[ones]}" if ones else _TENS[tens]


def rupees_in_words(rupees: int) -> str:
    """Whole rupees in the Indian system: 12,32,15,708 is "Twelve Crore Thirty Two Lakh Fifteen
    Thousand Seven Hundred Eight"."""
    if rupees == 0:
        return "Zero"
    crore, rest = divmod(rupees, 10**7)
    parts = [f"{rupees_in_words(crore)} Crore"] if crore else []
    for size, name in ((10**5, "Lakh"), (10**3, "Thousand"), (100, "Hundred")):
        count, rest = divmod(rest, size)
        if count:
            parts.append(f"{_below_hundred(count)} {name}")
    if rest:
        parts.append(_below_hundred(rest))
    return " ".join(parts)
