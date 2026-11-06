"""Grants (PRD M6-M8): loading fellowships, projects and certificates within scope, who may
manage them, and the ledger with its running balance. Visibility comes from scope.py; this
module only applies it. Writes: the research office anywhere, an admin over the unit; the PI
may add expenses to their own project (SECURITY.md §3)."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import ColumnElement, cast, exists, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.enums import LEDGER_HEADS, ModuleKey
from app.errors import ApiError, forbidden
from app.models import (
    Faculty,
    Fellowship,
    LedgerEntry,
    OrgUnit,
    Project,
    RoleAssignment,
    Scholar,
    User,
    UtilisationCertificate,
)
from app.models.base import Ltree
from app.modules import module_enabled
from app.notify import notify

LOW_BALANCE_SHARE = 0.10  # PRD M8: told when an expense takes the balance below 10% of received
IST = timezone(timedelta(hours=5, minutes=30))  # today's bill is not "future" just after midnight


def may_manage(principal: Principal, unit_path: str) -> bool:
    return "research_office" in principal.office_roles or principal.covers("admin", unit_path)


def require_manage(principal: Principal, unit_path: str) -> None:
    if not may_manage(principal, unit_path):
        raise forbidden()


async def require_module(session: AsyncSession, key: ModuleKey) -> None:
    if not await module_enabled(session, key):
        raise ApiError(404, "module_disabled", "This feature is not enabled.")


async def fellowship_or_403(
    session: AsyncSession, principal: Principal, fellowship_id: uuid.UUID
) -> tuple[Fellowship, Scholar, str]:
    """The fellowship, its scholar and the scholar's unit path."""
    await require_module(session, "fellowships")
    row = (
        await session.execute(
            select(Fellowship, Scholar, OrgUnit.path)
            .join(Scholar, Scholar.id == Fellowship.scholar_id)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .where(
                Fellowship.id == fellowship_id,
                Fellowship.deleted_at.is_(None),
                Scholar.deleted_at.is_(None),
                scope.scholar_predicate(principal, "fellowships"),
            )
        )
    ).first()
    if row is None:
        raise forbidden()
    return row[0], row[1], row[2]


async def project_or_403(
    session: AsyncSession, principal: Principal, project_id: uuid.UUID, *, ledger: bool = False
) -> tuple[Project, str]:
    """The project and its unit path; `ledger=True` also requires sight of its money."""
    await require_module(session, "projects")
    row = (
        await session.execute(
            select(Project, OrgUnit.path)
            .join(OrgUnit, OrgUnit.id == Project.unit_id)
            .where(
                Project.id == project_id,
                Project.deleted_at.is_(None),
                scope.project_predicate(principal, ledger=ledger),
            )
        )
    ).first()
    if row is None:
        raise forbidden()
    return row[0], row[1]


async def fellowship_ledger_or_403(
    session: AsyncSession, principal: Principal, fellowship_id: uuid.UUID
) -> tuple[Fellowship, str]:
    await require_module(session, "ledger")
    fellowship, scholar, path = await fellowship_or_403(session, principal, fellowship_id)
    visible = await session.scalar(
        select(
            exists().where(Scholar.id == scholar.id, scope.fellowship_ledger_predicate(principal))
        )
    )
    if not visible:
        raise forbidden()
    return fellowship, path


async def uc_or_403(
    session: AsyncSession, principal: Principal, uc_id: uuid.UUID
) -> tuple[UtilisationCertificate, str]:
    """A utilisation certificate, visible to whoever sees its project's ledger."""
    await require_module(session, "ledger")
    uc = await session.scalar(
        select(UtilisationCertificate).where(
            UtilisationCertificate.id == uc_id, UtilisationCertificate.deleted_at.is_(None)
        )
    )
    if uc is None:
        raise forbidden()
    _, path = await project_or_403(session, principal, uc.project_id, ledger=True)
    return uc, path


async def ledger_view(
    session: AsyncSession,
    *,
    owner: Project | Fellowship,
    can_manage: bool,
    can_add_expense: bool,
) -> dict[str, Any]:
    entries = await owner_entries(session, owner)
    received = spent = 0.0
    rows = []
    for e in entries:
        if e.entry_kind == "disbursement":
            received += e.amount
        else:
            spent += e.amount
        rows.append(
            {
                "id": e.id,
                "entry_kind": e.entry_kind,
                "head": e.head,
                "amount": e.amount,
                "entry_date": e.entry_date,
                "reference": e.reference,
                "note": e.note,
                "balance": round(received - spent, 2),
            }
        )
    return {
        "entries": rows,
        "received": round(received, 2),
        "spent": round(spent, 2),
        "balance": round(received - spent, 2),
        "sanctioned": owner.amount_sanctioned if isinstance(owner, Project) else None,
        "can_manage": can_manage,
        "can_add_expense": can_add_expense,
    }


def check_dates(start: date, end: date, srf_upgrade_on: date | None = None) -> None:
    """Checked on the merged values before a partial update is written."""
    if end < start:
        raise ApiError(422, "invalid_dates", "The end date is before the start date.")
    if srf_upgrade_on is not None and not start <= srf_upgrade_on <= end:
        raise ApiError(
            422, "invalid_dates", "The SRF upgrade date must fall within the fellowship."
        )


async def _entries(session: AsyncSession, owned: ColumnElement[bool]) -> list[LedgerEntry]:
    return list(
        (
            await session.scalars(
                select(LedgerEntry)
                .where(owned, LedgerEntry.deleted_at.is_(None))
                .order_by(LedgerEntry.entry_date, LedgerEntry.created_at)
            )
        ).all()
    )


async def project_entries(session: AsyncSession, project_id: uuid.UUID) -> list[LedgerEntry]:
    return await _entries(session, LedgerEntry.project_id == project_id)


async def owner_entries(session: AsyncSession, owner: Project | Fellowship) -> list[LedgerEntry]:
    if isinstance(owner, Project):
        return await project_entries(session, owner.id)
    return await _entries(session, LedgerEntry.fellowship_id == owner.id)


def _total(entries: list[LedgerEntry], kind: str) -> float:
    return round(sum(e.amount for e in entries if e.entry_kind == kind), 2)


def _by_head(entries: list[LedgerEntry]) -> dict[str, float]:
    spent = {h: _total([e for e in entries if e.head == h], "expense") for h in LEDGER_HEADS}
    return {h: amount for h, amount in spent.items() if amount}


async def pi_and_office_user_ids(session: AsyncSession, project: Project) -> list[uuid.UUID]:
    pi_user = await session.scalar(select(Faculty.user_id).where(Faculty.id == project.pi_id))
    office = await session.scalars(
        select(RoleAssignment.user_id).where(
            RoleAssignment.role == "research_office", RoleAssignment.deleted_at.is_(None)
        )
    )
    return [u for u in (pi_user, *office) if u]


def inr(amount: float) -> str:
    """₹ with lakh and crore grouping, paise only when there are some, as the web shows it."""
    whole, paise = f"{abs(amount):.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    while head:
        tail = f"{head[-2:]},{tail}"
        head = head[:-2]
    return f"{'-' if amount < 0 else ''}₹{tail}{'' if paise == '00' else '.' + paise}"


def _day(value: date) -> str:
    return value.strftime("%-d %b %Y")


def ledger_warnings(
    owner: Project | Fellowship,
    entries: list[LedgerEntry],
    *,
    kind: str,
    amount: float,
    on: date,
) -> dict[str, str]:
    """What looks wrong with a new entry, by code. It may still be true (money spent ahead of
    an instalment, a backfilled record), so the person confirms rather than being blocked."""
    warnings: dict[str, str] = {}
    if kind == "expense":
        spent = round(_total(entries, "expense") + amount, 2)
        balance = round(_total(entries, "disbursement") - spent, 2)
        if balance < 0:
            warnings["over_balance"] = f"This takes the balance to {inr(balance)}."
        if isinstance(owner, Project) and spent > owner.amount_sanctioned:
            warnings["over_sanction"] = (
                f"Total spending would exceed the {inr(owner.amount_sanctioned)} sanctioned."
            )
    what = "project" if isinstance(owner, Project) else "fellowship"
    if on > datetime.now(IST).date():
        warnings["future_date"] = "This date is in the future."
    elif on < owner.start_date:
        warnings["outside_period"] = (
            f"This date is before the {what} started on {_day(owner.start_date)}."
        )
    elif on > owner.end_date:
        warnings["outside_period"] = (
            f"This date is after the {what} ended on {_day(owner.end_date)}."
        )
    return warnings


async def _nearest_admin_ids(
    session: AsyncSession, unit_path: str, *, excluding: uuid.UUID
) -> list[uuid.UUID]:
    """The admins of the closest unit at or above `unit_path` with one other than `excluding`,
    so the department hears first and a department with no admin of its own is still covered."""
    rows = (
        await session.execute(
            select(RoleAssignment.user_id, func.nlevel(OrgUnit.path))
            .join(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
            .where(
                RoleAssignment.role == "admin",
                RoleAssignment.deleted_at.is_(None),
                RoleAssignment.user_id != excluding,
                OrgUnit.deleted_at.is_(None),
                OrgUnit.path.op("@>")(cast(literal(unit_path), Ltree)),
            )
        )
    ).all()
    nearest = max((level for _, level in rows), default=None)
    return [user_id for user_id, level in rows if level == nearest]


async def _owner_label(session: AsyncSession, owner: Project | Fellowship) -> tuple[str, str]:
    """A short name for the owner and what the alert should say about who it belongs to."""
    if isinstance(owner, Project):
        pi = await session.scalar(
            select(User.full_name)
            .join(Faculty, Faculty.user_id == User.id)
            .where(Faculty.id == owner.pi_id)
        )
        return owner.title, f"project {owner.title} (PI {pi})"
    scholar = await session.scalar(
        select(User.full_name)
        .join(Scholar, Scholar.user_id == User.id)
        .where(Scholar.id == owner.scholar_id)
    )
    return f"fellowship of {scholar}", f"the fellowship of {scholar}"


async def alert_confirmed(
    session: AsyncSession,
    principal: Principal,
    owner: Project | Fellowship,
    unit_path: str,
    *,
    amount: float,
    on: date,
    warnings: dict[str, str],
) -> None:
    """Someone saved an entry despite its warnings: the department's admin hears who and what,
    so a second person looks at it. The person who confirmed is never the one told."""
    short, full = await _owner_label(session, owner)
    notify(
        session,
        await _nearest_admin_ids(session, unit_path, excluding=principal.user_id),
        "grant_alert",
        f"Ledger entry confirmed: {short}",
        f"{principal.full_name} confirmed an entry of {inr(amount)} dated {_day(on)} on {full}. "
        + " ".join(warnings.values()),
        f"/projects/{owner.id}" if isinstance(owner, Project) else "/fellowships",
    )


async def alert_if_low(session: AsyncSession, project: Project, expense: float) -> None:
    """After an expense: tell the PI and the research office once, as it takes the unspent
    balance below LOW_BALANCE_SHARE of the amount received (PRD M8), or as the first money
    goes out with none recorded as received."""
    entries = await project_entries(session, project.id)
    received = _total(entries, "disbursement")
    spent = _total(entries, "expense")
    balance = round(received - spent, 2)
    floor = received * LOW_BALANCE_SHARE
    low = received > 0 and balance < floor <= balance + expense
    unfunded = received == 0 and spent == expense
    if not (low or unfunded):
        return
    notify(
        session,
        await pi_and_office_user_ids(session, project),
        "grant_alert",
        f"{'Funds running low' if low else 'Spending with no money received'}: {project.title}",
        f"Unspent balance is {inr(balance)} of {inr(received)} received "
        f"(below {LOW_BALANCE_SHARE:.0%}). Ask the agency for the next instalment in time."
        if low
        else f"{inr(spent)} was spent before any money was recorded as received. "
        "Record the money received, or check the entry.",
        f"/projects/{project.id}",
    )


async def uc_figures(session: AsyncSession, uc: UtilisationCertificate) -> dict[str, Any]:
    """The GFR 12-A figures for one UC period, from the ledger (PRD M8)."""
    entries = await project_entries(session, uc.project_id)
    before = [e for e in entries if e.entry_date < uc.period_start]
    during = [e for e in entries if uc.period_start <= e.entry_date <= uc.period_end]
    opening = round(_total(before, "disbursement") - _total(before, "expense"), 2)
    received = _total(during, "disbursement")
    spent = _total(during, "expense")
    to_date = before + during
    return {
        "opening_balance": opening,
        "grants_received": [
            {"date": e.entry_date, "reference": e.reference, "amount": e.amount}
            for e in during
            if e.entry_kind == "disbursement"
        ],
        "received": received,
        "available": round(opening + received, 2),
        "spent_by_head": _by_head(during),
        "spent": spent,
        "closing_balance": round(opening + received - spent, 2),
        "received_to_date": _total(to_date, "disbursement"),
        "spent_to_date": _total(to_date, "expense"),
    }
