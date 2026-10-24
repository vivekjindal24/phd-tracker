"""Grant ledger (PRD M8, UX Flow 11): money in (disbursements) and out (expenses) against a
project or a fellowship, with a running balance, and a project's utilisation certificates per
period. A record, not a payment system (PRD §7). Admins over the unit and the research office
manage it; the PI may add expenses to their own project; heads read their subtree."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import grants
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.errors import forbidden
from app.models import Fellowship, LedgerEntry, Project, UtilisationCertificate
from app.modules import require_module
from app.rbac import require_perm
from app.schemas.grants import LedgerEntryIn, LedgerView, UcIn, UcOut, UcUpdate

router = APIRouter(tags=["ledger"], dependencies=[Depends(require_module("ledger"))])


async def _owner(
    session: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID | None,
    fellowship_id: uuid.UUID | None,
) -> tuple[Project | Fellowship, bool, bool]:
    """The entry's owner, whether the caller manages it, and whether they may add expenses."""
    if project_id is not None:
        project, path = await grants.project_or_403(session, principal, project_id, ledger=True)
        manage = grants.may_manage(principal, path)
        return project, manage, manage or project.pi_id == principal.faculty_id
    assert fellowship_id is not None
    fellowship, path = await grants.fellowship_ledger_or_403(session, principal, fellowship_id)
    manage = grants.may_manage(principal, path)
    return fellowship, manage, manage


async def _view(
    session: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID | None = None,
    fellowship_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    owner, manage, add_expense = await _owner(session, principal, project_id, fellowship_id)
    return await grants.ledger_view(
        session, owner=owner, can_manage=manage, can_add_expense=add_expense
    )


@router.get("/projects/{project_id}/ledger", response_model=LedgerView)
async def project_ledger(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_principal),  # scope decides (the PI included)
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _view(session, principal, project_id=project_id)


@router.get("/fellowships/{fellowship_id}/ledger", response_model=LedgerView)
async def fellowship_ledger(
    fellowship_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _view(session, principal, fellowship_id=fellowship_id)


@router.post("/ledger", response_model=LedgerView, status_code=201)
async def add_entry(
    body: LedgerEntryIn,
    principal: Principal = Depends(current_principal),  # the PI may add expenses
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _, manage, add_expense = await _owner(session, principal, body.project_id, body.fellowship_id)
    if not (manage or (add_expense and body.entry_kind == "expense")):
        raise forbidden()
    await insert(session, principal, LedgerEntry(**body.model_dump()))
    await session.commit()
    return await _view(session, principal, body.project_id, body.fellowship_id)


@router.delete("/ledger/{entry_id}", response_model=LedgerView)
async def remove_entry(
    entry_id: uuid.UUID,
    principal: Principal = Depends(require_perm("ledger", "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Corrections are a removal and a fresh entry; the audit log keeps both."""
    entry = await session.scalar(
        select(LedgerEntry).where(LedgerEntry.id == entry_id, LedgerEntry.deleted_at.is_(None))
    )
    if entry is None:
        raise forbidden()
    _, manage, _ = await _owner(session, principal, entry.project_id, entry.fellowship_id)
    if not manage:
        raise forbidden()
    await soft_delete(session, principal, entry)
    await session.commit()
    return await _view(session, principal, entry.project_id, entry.fellowship_id)


# --- utilisation certificates --------------------------------------------------------------


def _uc(uc: UtilisationCertificate) -> UcOut:
    return UcOut(
        id=uc.id,
        period_start=uc.period_start,
        period_end=uc.period_end,
        submitted_on=uc.submitted_on,
    )


@router.get("/projects/{project_id}/ucs", response_model=list[UcOut])
async def list_ucs(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[UcOut]:
    await grants.project_or_403(session, principal, project_id, ledger=True)
    rows = await session.scalars(
        select(UtilisationCertificate)
        .where(
            UtilisationCertificate.project_id == project_id,
            UtilisationCertificate.deleted_at.is_(None),
        )
        .order_by(UtilisationCertificate.period_start.desc())
    )
    return [_uc(uc) for uc in rows]


@router.post("/projects/{project_id}/ucs", response_model=UcOut, status_code=201)
async def add_uc(
    project_id: uuid.UUID,
    body: UcIn,
    principal: Principal = Depends(require_perm("ledger", "create")),
    session: AsyncSession = Depends(get_session),
) -> UcOut:
    _, path = await grants.project_or_403(session, principal, project_id, ledger=True)
    grants.require_manage(principal, path)
    uc = await insert(
        session, principal, UtilisationCertificate(project_id=project_id, **body.model_dump())
    )
    await session.commit()
    return _uc(uc)


@router.patch("/ucs/{uc_id}", response_model=UcOut)
async def update_uc(
    uc_id: uuid.UUID,
    body: UcUpdate,
    principal: Principal = Depends(require_perm("ledger", "update")),
    session: AsyncSession = Depends(get_session),
) -> UcOut:
    uc, path = await grants.uc_or_403(session, principal, uc_id)
    grants.require_manage(principal, path)
    await update(session, principal, uc, body.model_dump())
    await session.commit()
    return _uc(uc)


@router.delete("/ucs/{uc_id}", status_code=204)
async def remove_uc(
    uc_id: uuid.UUID,
    principal: Principal = Depends(require_perm("ledger", "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    uc, path = await grants.uc_or_403(session, principal, uc_id)
    grants.require_manage(principal, path)
    await soft_delete(session, principal, uc)
    await session.commit()
