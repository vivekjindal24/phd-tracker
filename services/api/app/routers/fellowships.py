"""Fellowships (PRD M6, UX Flow 11): an admin over the scholar's unit or the research office
records scheme, amounts and dates, and the JRF→SRF upgrade; scholars see their own, supervisors
their scholars'. The money paid out sits in the ledger (routers/ledger.py)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import grants, scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import FellowshipStatus
from app.errors import forbidden
from app.models import Fellowship, OrgUnit, Scholar, User
from app.modules import module_enabled, require_module
from app.rbac import require_perm
from app.schemas import Ref
from app.schemas.grants import FellowshipIn, FellowshipOut, FellowshipUpdate

router = APIRouter(
    prefix="/fellowships",
    tags=["fellowships"],
    dependencies=[Depends(require_module("fellowships"))],
)


def _query(principal: Principal) -> Select:
    return (
        select(
            Fellowship,
            Scholar,
            User.full_name,
            OrgUnit.name,
            OrgUnit.path,
            scope.fellowship_ledger_predicate(principal).label("sees_ledger"),
        )
        .join(Scholar, Scholar.id == Fellowship.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .where(
            Fellowship.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "fellowships"),
        )
    )


def _out(row, principal: Principal, ledger_on: bool) -> FellowshipOut:
    f, s, name, unit_name, path, sees_ledger = row
    return FellowshipOut(
        id=f.id,
        scholar=Ref(id=s.id, name=name),
        roll_number=s.roll_number,
        unit=Ref(id=s.unit_id, name=unit_name),
        scheme=f.scheme,
        amount_monthly=f.amount_monthly,
        hra_amount=f.hra_amount,
        start_date=f.start_date,
        end_date=f.end_date,
        srf_upgrade_on=f.srf_upgrade_on,
        status=f.status,
        can_manage=grants.may_manage(principal, path),
        sees_ledger=ledger_on and bool(sees_ledger),
    )


async def _one(session: AsyncSession, principal: Principal, fellowship_id: uuid.UUID):
    row = (await session.execute(_query(principal).where(Fellowship.id == fellowship_id))).first()
    if row is None:
        raise forbidden()
    return _out(row, principal, await module_enabled(session, "ledger"))


@router.get("", response_model=list[FellowshipOut])
async def list_fellowships(
    scholar_id: uuid.UUID | None = None,
    status: FellowshipStatus | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    principal: Principal = Depends(require_perm("fellowships", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[FellowshipOut]:
    stmt = _query(principal)
    if scholar_id:
        stmt = stmt.where(Fellowship.scholar_id == scholar_id)
    if status:
        stmt = stmt.where(Fellowship.status == status)
    rows = await session.execute(
        stmt.order_by(Fellowship.end_date.desc(), User.full_name).limit(limit)
    )
    ledger_on = await module_enabled(session, "ledger")
    return [_out(r, principal, ledger_on) for r in rows]


@router.post("", response_model=FellowshipOut, status_code=201)
async def create_fellowship(
    body: FellowshipIn,
    principal: Principal = Depends(require_perm("fellowships", "create")),
    session: AsyncSession = Depends(get_session),
) -> FellowshipOut:
    scholar = await scope.get_scholar_or_403(session, principal, body.scholar_id, "fellowships")
    grants.require_manage(principal, await scope.unit_path(session, scholar.unit_id))
    f = await insert(session, principal, Fellowship(**body.model_dump()))
    await session.commit()
    return await _one(session, principal, f.id)


@router.patch("/{fellowship_id}", response_model=FellowshipOut)
async def update_fellowship(
    fellowship_id: uuid.UUID,
    body: FellowshipUpdate,
    principal: Principal = Depends(require_perm("fellowships", "update")),
    session: AsyncSession = Depends(get_session),
) -> FellowshipOut:
    f, _, path = await grants.fellowship_or_403(session, principal, fellowship_id)
    grants.require_manage(principal, path)
    changes = body.model_dump(exclude_unset=True)
    for required in ("scheme", "amount_monthly", "hra_amount", "start_date", "end_date", "status"):
        if changes.get(required, ...) is None:
            changes.pop(required)  # null clears only the upgrade date
    merged = {
        k: changes.get(k, getattr(f, k)) for k in ("start_date", "end_date", "srf_upgrade_on")
    }
    grants.check_dates(merged["start_date"], merged["end_date"], merged["srf_upgrade_on"])
    await update(session, principal, f, changes)
    await session.commit()
    return await _one(session, principal, fellowship_id)


@router.delete("/{fellowship_id}", status_code=204)
async def delete_fellowship(
    fellowship_id: uuid.UUID,
    principal: Principal = Depends(require_perm("fellowships", "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    f, _, path = await grants.fellowship_or_403(session, principal, fellowship_id)
    grants.require_manage(principal, path)
    await soft_delete(session, principal, f)
    await session.commit()
