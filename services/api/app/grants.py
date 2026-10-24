"""Grants (PRD M6-M8): loading fellowships, projects and certificates within scope, who may
manage them, and the ledger with its running balance. Visibility comes from scope.py; this
module only applies it. Writes: the research office anywhere, an admin over the unit; the PI
may add expenses to their own project (SECURITY.md §3)."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.enums import ModuleKey
from app.errors import ApiError, forbidden
from app.models import (
    Fellowship,
    LedgerEntry,
    OrgUnit,
    Project,
    Scholar,
    UtilisationCertificate,
)
from app.modules import module_enabled


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
    column = LedgerEntry.project_id if isinstance(owner, Project) else LedgerEntry.fellowship_id
    entries = (
        await session.scalars(
            select(LedgerEntry)
            .where(column == owner.id, LedgerEntry.deleted_at.is_(None))
            .order_by(LedgerEntry.entry_date, LedgerEntry.created_at)
        )
    ).all()
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
