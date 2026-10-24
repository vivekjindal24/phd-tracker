"""Bulk import of faculty, scholars and RDC-register history (PRD F16, UX Flow 5).

Every row is checked first against the same rules as the forms (scope, UGC caps, unique email
and roll number); the admin sees every problem with its row and column. Only a clean file is
written, in one transaction, through the same functions the forms use. Rows already in the
system are reported and skipped, so a file can be fixed and re-uploaded safely."""

import logging
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import directory
from app.auth import service as auth_service
from app.auth.principal import Principal
from app.crud import insert
from app.enums import (
    APPROVAL_BODIES,
    DESIGNATIONS,
    MILESTONE_STATUSES,
    MILESTONE_TYPES,
    STAGES,
    UGC_CAP,
)
from app.models import Faculty, Milestone, OrgUnit, Scholar, Settings, User
from app.notify import email_configured
from app.spreadsheet import Column, Row, parse_date

log = logging.getLogger("anveshan.import")

FACULTY = (
    Column("name", "Name", True, "Full name as it should appear.", "Dr. Meera Iyer"),
    Column("email", "Email", True, "University email — their login.", "meera.iyer@univ.ac.in"),
    Column("designation", "Designation", True, ", ".join(DESIGNATIONS) + ".", "Professor"),
    Column("unit", "Unit", True, "Department code (or exact name) from Settings.", "CSE"),
    Column("employee_id", "Employee ID", False, "Optional.", "EMP-1042"),
    Column(
        "max_scholars",
        "Max scholars",
        False,
        "Optional; blank = the UGC limit (8 / 6 / 4). May be lower, never higher.",
        "6",
    ),
    Column("can_supervise", "Can supervise", False, "yes / no; blank = yes.", "yes"),
)
SCHOLARS = (
    Column("roll_number", "Roll number", True, "Unique registration number.", "PHD-CSE-2023-07"),
    Column("name", "Name", True, "Full name.", "Arjun Rao"),
    Column("email", "Email", True, "University email — their login.", "arjun.rao@univ.ac.in"),
    Column("unit", "Unit", True, "Department code (or exact name).", "CSE"),
    Column(
        "supervisor_email",
        "Supervisor email",
        False,
        "Must already be in Anveshan as faculty (import faculty first).",
        "meera.iyer@univ.ac.in",
    ),
    Column(
        "co_supervisor_email",
        "Co-supervisor email",
        False,
        "Only when co-supervision is switched on.",
        "",
    ),
    Column("stage", "Stage", False, ", ".join(STAGES) + ". Blank = Registered.", "Coursework"),
    Column(
        "admission_date",
        "Admission date",
        False,
        "Day first: 15/07/2023 or 2023-07-15.",
        "15/07/2023",
    ),
    Column("research_title", "Research title", False, "Optional.", "Graph learning for…"),
)
HISTORY = (
    Column(
        "roll_number", "Roll number", True, "Scholar must already be imported.", "PHD-CSE-2023-07"
    ),
    Column(
        "milestone",
        "Milestone",
        True,
        "coursework, proposal approval, RAC review, pre-synopsis, thesis submission, viva, "
        "degree awarded.",
        "proposal approval",
    ),
    Column(
        "status", "Status", False, "Approved / Pending / Rejected; blank = Approved.", "Approved"
    ),
    Column("approval_body", "Approval body", True, ", ".join(APPROVAL_BODIES) + ".", "RDC"),
    Column(
        "resolution_number", "Resolution number", False, "As in the minute book.", "RDC/2023/14"
    ),
    Column("resolution_date", "Resolution date", False, "Day first.", "22/09/2023"),
    Column("notes", "Notes", False, "Optional.", ""),
)
KINDS: dict[str, tuple[Column, ...]] = {
    "faculty": FACULTY,
    "scholars": SCHOLARS,
    "history": HISTORY,
}
YES = {"yes", "y", "true", "1"}
NO = {"no", "n", "false", "0"}


@dataclass
class Report:
    kind: str
    dry_run: bool
    total_rows: int
    to_create: int = 0
    created: int = 0
    already_present: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    invitations_sent: int | None = None
    invitations_failed: list[str] = field(default_factory=list)


Apply = Callable[[], Awaitable[User | None]]


class _Check:
    """Reads one row's cells, collecting every problem rather than stopping at the first."""

    def __init__(self, row: Row, columns: tuple[Column, ...], report: Report) -> None:
        self.row, self.report = row, report
        self.headers = {c.key: c.header for c in columns}
        self.ok = True

    def error(self, key: str, message: str) -> None:
        self.ok = False
        self.report.errors.append(
            {"row": self.row.number, "column": self.headers[key], "message": message}
        )

    def text(self, key: str, max_len: int, required: bool = False) -> str | None:
        value = self.row.values.get(key)
        if isinstance(value, date):
            value = value.isoformat()
        if value is None:
            if required:
                self.error(key, "is required")
            return None
        if len(value) > max_len:
            self.error(key, f"is longer than {max_len} characters")
            return None
        return value

    def email(self, key: str, required: bool = False) -> str | None:
        value = self.text(key, 254, required)
        if value is None:
            return None
        try:
            return validate_email(value, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            self.error(key, f"{value!r} is not an email address")
            return None

    def choice(self, key: str, options: tuple[str, ...], required: bool = False) -> str | None:
        value = self.text(key, 100, required)
        if value is None:
            return None
        wanted = " ".join(value.replace("_", " ").replace("-", " ").lower().split())
        for option in options:
            if " ".join(option.replace("_", " ").replace("-", " ").lower().split()) == wanted:
                return option
        self.error(key, f"{value!r} is not one of: {', '.join(options)}")
        return None

    def day(self, key: str) -> date | None:
        try:
            return parse_date(self.row.values.get(key))  # type: ignore[arg-type]
        except ValueError as exc:
            self.error(key, str(exc))
            return None


class _Context:
    """Lookups shared by every row of one file, loaded once."""

    def __init__(self, session: AsyncSession, principal: Principal) -> None:
        self.session, self.principal = session, principal
        self.units_by_code: dict[str, OrgUnit] = {}
        self.units_by_name: dict[str, list[OrgUnit]] = {}

    async def load_units(self) -> None:
        for unit in await self.session.scalars(select(OrgUnit).where(OrgUnit.deleted_at.is_(None))):
            self.units_by_code[unit.code.lower()] = unit
            self.units_by_name.setdefault(unit.name.lower(), []).append(unit)

    def unit(self, check: _Check, key: str = "unit") -> OrgUnit | None:
        value = check.text(key, 200, required=True)
        if value is None:
            return None
        unit = self.units_by_code.get(value.lower())
        if unit is None:
            named = self.units_by_name.get(value.lower(), [])
            unit = named[0] if len(named) == 1 else None
        if unit is None:
            check.error(key, f"no unit with code or name {value!r}")
            return None
        if not self.principal.covers("admin", unit.path):
            check.error(key, f"{unit.name} is outside the units you manage")
            return None
        return unit

    async def existing_emails(self, emails: list[str]) -> set[str]:
        rows = await self.session.scalars(
            select(User.email).where(User.email.in_(emails), User.deleted_at.is_(None))
        )
        return {e.lower() for e in rows}


def _raw(row: Row, key: str) -> str:
    value = row.values.get(key)
    return value.lower() if isinstance(value, str) else ""


def _duplicates(rows: list[Row], key: str) -> set[int]:
    """Row numbers whose `key` repeats an earlier row of the same file."""
    seen: set[str] = set()
    repeated = set()
    for row in rows:
        value = row.values.get(key)
        if isinstance(value, str):
            if value.lower() in seen:
                repeated.add(row.number)
            seen.add(value.lower())
    return repeated


async def _plan_faculty(ctx: _Context, rows: list[Row], report: Report) -> list[Apply]:
    present = await ctx.existing_emails(
        [str(r.values["email"]) for r in rows if isinstance(r.values.get("email"), str)]
    )
    repeated = _duplicates(rows, "email")
    plan: list[Apply] = []
    for row in rows:
        if _raw(row, "email") in present:
            report.already_present.append({"row": row.number, "what": _raw(row, "email")})
            continue
        c = _Check(row, FACULTY, report)
        name, email = c.text("name", 200, True), c.email("email", True)
        designation = c.choice("designation", DESIGNATIONS, True)
        unit = ctx.unit(c)
        employee_id = c.text("employee_id", 50)
        cap = UGC_CAP.get(designation or "", 0)
        raw_cap = c.text("max_scholars", 3)
        if raw_cap is not None:
            if not raw_cap.isdigit():
                c.error("max_scholars", "must be a whole number")
            elif designation and int(raw_cap) > cap:
                c.error("max_scholars", f"UGC allows at most {cap} for a {designation}")
            else:
                cap = int(raw_cap)
        supervise = (c.text("can_supervise", 5) or "yes").lower()
        if supervise not in YES | NO:
            c.error("can_supervise", "use yes or no")
        if row.number in repeated:
            c.error("email", "appears earlier in this file")
        if not c.ok:
            continue
        assert name and email and designation and unit
        profile = Faculty(
            unit_id=unit.id,
            designation=designation,
            employee_id=employee_id,
            max_scholars=cap,
            can_supervise=supervise in YES,
        )
        plan.append(_person(ctx, email, name, faculty=profile))
    return plan


def _person(
    ctx: _Context,
    email: str,
    name: str,
    *,
    faculty: Faculty | None = None,
    scholar: Scholar | None = None,
) -> Apply:
    async def apply() -> User:
        return await directory.create_person(
            ctx.session,
            ctx.principal,
            email=email,
            full_name=name,
            password_hash=None,
            faculty=faculty,
            scholar=scholar,
        )

    return apply


async def _supervisors(ctx: _Context, emails: set[str]) -> dict[str, tuple[Faculty, int]]:
    """Faculty by email with their current supervision load."""
    if not emails:
        return {}
    load = directory.load_of_faculty()
    rows = await ctx.session.execute(
        select(Faculty, User.email, load)
        .join(User, User.id == Faculty.user_id)
        .where(
            User.email.in_(list(emails)), Faculty.deleted_at.is_(None), User.deleted_at.is_(None)
        )
    )
    return {email.lower(): (f, n) for f, email, n in rows}


async def _plan_scholars(ctx: _Context, rows: list[Row], report: Report) -> list[Apply]:
    emails = [str(r.values["email"]) for r in rows if isinstance(r.values.get("email"), str)]
    present = await ctx.existing_emails(emails)
    rolls = [str(r.values["roll_number"]) for r in rows if r.values.get("roll_number")]
    present_rolls = set(
        await ctx.session.scalars(
            select(Scholar.roll_number).where(
                Scholar.roll_number.in_(rolls), Scholar.deleted_at.is_(None)
            )
        )
    )
    sup_emails = {
        str(r.values[k]).lower()
        for r in rows
        for k in ("supervisor_email", "co_supervisor_email")
        if isinstance(r.values.get(k), str)
    }
    faculty = await _supervisors(ctx, sup_emails)
    co_mode = await ctx.session.scalar(select(Settings.co_supervision).where(Settings.id == 1))
    assigned: Counter[uuid.UUID] = Counter()  # supervision added by earlier rows of this file
    repeated_email, repeated_roll = _duplicates(rows, "email"), _duplicates(rows, "roll_number")
    plan: list[Apply] = []
    for row in rows:
        roll_raw = row.values.get("roll_number")
        if _raw(row, "email") in present or roll_raw in present_rolls:
            what = roll_raw if isinstance(roll_raw, str) else _raw(row, "email")
            report.already_present.append({"row": row.number, "what": what})
            continue
        c = _Check(row, SCHOLARS, report)
        roll, name = c.text("roll_number", 50, True), c.text("name", 200, True)
        email, unit = c.email("email", True), ctx.unit(c)
        stage = c.choice("stage", STAGES) or "Registered"
        admitted, title = c.day("admission_date"), c.text("research_title", 500)
        sup, sup_load = _faculty_ref(c, faculty, "supervisor_email")
        co, _ = _faculty_ref(c, faculty, "co_supervisor_email")
        if co and co_mode == "off":
            c.error("co_supervisor_email", "co-supervision is switched off for this university")
        if sup and co and sup.id == co.id:
            c.error("co_supervisor_email", "must be someone other than the supervisor")
        if row.number in repeated_email:
            c.error("email", "appears earlier in this file")
        if row.number in repeated_roll:
            c.error("roll_number", "appears earlier in this file")
        current = stage != directory.COMPLETED_STAGE  # a completed scholar is history: no cap
        if sup is not None:
            load = sup_load + assigned[sup.id]
            if not sup.can_supervise:
                c.error("supervisor_email", "this faculty member is not a supervisor")
            elif current and load >= sup.max_scholars:
                c.error(
                    "supervisor_email",
                    f"already guides {load} scholars — the UGC limit is {sup.max_scholars}",
                )
            elif c.ok and current:
                assigned[sup.id] += 1
        if not c.ok:
            continue
        assert roll and name and email and unit
        profile = Scholar(
            unit_id=unit.id,
            roll_number=roll,
            stage=stage,
            admission_date=admitted,
            research_title=title,
        )
        plan.append(_scholar_with_guides(ctx, email, name, profile, sup, co))
    return plan


def _faculty_ref(
    c: _Check, faculty: dict[str, tuple[Faculty, int]], key: str
) -> tuple[Faculty | None, int]:
    """The faculty member a column names, with their current supervision load."""
    email = c.email(key)
    if email is None:
        return None, 0
    found = faculty.get(email)
    if found is None:
        c.error(key, f"no faculty member with email {email}")
        return None, 0
    return found


def _scholar_with_guides(
    ctx: _Context, email: str, name: str, profile: Scholar, sup: Faculty | None, co: Faculty | None
) -> Apply:
    async def apply() -> User:
        user = await _person(ctx, email, name, scholar=profile)()
        # The same cap check (row-locked) the profile page uses; a race fails the whole file.
        if sup is not None:
            await directory.assign_supervisor(
                ctx.session, ctx.principal, profile, sup.id, announce=False
            )
        if co is not None:
            await directory.assign_co_supervisor(ctx.session, ctx.principal, profile, co.id)
        return user

    return apply


async def _plan_history(ctx: _Context, rows: list[Row], report: Report) -> list[Apply]:
    rolls = [str(r.values["roll_number"]) for r in rows if r.values.get("roll_number")]
    scholars = {
        s.roll_number: (s, path)
        for s, path in await ctx.session.execute(
            select(Scholar, OrgUnit.path)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .where(Scholar.roll_number.in_(rolls), Scholar.deleted_at.is_(None))
        )
    }
    known = {
        (m.scholar_id, m.milestone_type, m.resolution_number, m.resolution_date)
        for m in await ctx.session.scalars(
            select(Milestone).where(
                Milestone.scholar_id.in_([s.id for s, _ in scholars.values()]),
                Milestone.deleted_at.is_(None),
            )
        )
    }
    plan: list[Apply] = []
    for row in rows:
        c = _Check(row, HISTORY, report)
        roll = c.text("roll_number", 50, True)
        kind = c.choice("milestone", MILESTONE_TYPES, True)
        status = c.choice("status", MILESTONE_STATUSES) or "Approved"
        body = c.choice("approval_body", APPROVAL_BODIES, True)
        number, when = c.text("resolution_number", 100), c.day("resolution_date")
        notes = c.text("notes", 4000) or ""
        found = scholars.get(roll or "")
        if roll and found is None:
            c.error("roll_number", f"no scholar with roll number {roll} (import scholars first)")
        elif found and not ctx.principal.covers("admin", found[1]):
            c.error("roll_number", "this scholar is outside the units you manage")
        if not c.ok:
            continue
        assert found and kind and body
        key = (found[0].id, kind, number, when)
        if key in known:
            report.already_present.append({"row": row.number, "what": f"{roll} {kind}"})
            continue
        known.add(key)  # a repeat later in the same file is skipped, not imported twice
        milestone = Milestone(
            scholar_id=found[0].id,
            milestone_type=kind,
            status=status,
            approval_body=body,
            resolution_number=number,
            resolution_date=when,
            notes=notes,
        )
        plan.append(_milestone(ctx, milestone))
    return plan


def _milestone(ctx: _Context, milestone: Milestone) -> Apply:
    async def apply() -> None:
        await insert(ctx.session, ctx.principal, milestone)

    return apply


PLANNERS = {"faculty": _plan_faculty, "scholars": _plan_scholars, "history": _plan_history}


async def run(
    session: AsyncSession,
    principal: Principal,
    kind: str,
    rows: list[Row],
    *,
    dry_run: bool,
    send_invitations: bool,
) -> Report:
    if send_invitations and not dry_run and not email_configured():
        raise auth_service.EMAIL_NOT_CONFIGURED
    report = Report(kind=kind, dry_run=dry_run, total_rows=len(rows))
    ctx = _Context(session, principal)
    await ctx.load_units()
    plan = await PLANNERS[kind](ctx, rows, report)
    report.to_create = len(plan)
    if dry_run or report.errors:
        await session.rollback()
        return report
    users = [u for u in [await apply() for apply in plan] if u is not None]
    links = []
    if send_invitations:
        links = [
            (u, await auth_service.issue_password_link(session, u.id, "invite")) for u in users
        ]
    await session.commit()
    report.created = len(plan)
    if send_invitations:
        report.invitations_sent = 0
        for user, raw in links:
            try:
                await auth_service.email_password_link(user, raw, "invite")
                report.invitations_sent += 1
            except Exception:
                log.exception("invitation email to user %s failed", user.id)
                report.invitations_failed.append(user.email)
    return report
