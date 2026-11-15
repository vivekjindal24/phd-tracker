"""Fellowship monthly claims (PRD M6, UX Flow 11): the scholar claims one month of their own
active fellowship; the fellowship_claim chain certifies it. Workflow actions live on /items.
A claim records who vouched for the month — what was paid stays in the ledger (PRD §7)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import grants, items, scope, workflow
from app.auth.principal import Principal
from app.crud import insert, update
from app.db import get_session
from app.enums import ITEM_STATES, ItemState
from app.errors import ApiError, forbidden
from app.models import Fellowship, FellowshipClaim, Scholar, User
from app.modules import require_module
from app.rbac import require_perm
from app.schemas import ItemView
from app.schemas.grants import ClaimIn, ClaimRow, ClaimUpdate
from app.sorting import Sort, ordered, page_of, ranked

router = APIRouter(
    prefix="/fellowship-claims",
    tags=["fellowships"],
    dependencies=[Depends(require_module("fellowships"))],
)


@router.get("", response_model=list[ClaimRow])
async def list_claims(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    state: ItemState | None = None,
    scholar_id: uuid.UUID | None = None,
    fellowship_id: uuid.UUID | None = None,
    sort: Sort = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_perm("fellowship_claims", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(FellowshipClaim, Fellowship.scheme, User.full_name)
        .join(Fellowship, Fellowship.id == FellowshipClaim.fellowship_id)
        .join(Scholar, Scholar.id == FellowshipClaim.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .where(
            FellowshipClaim.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "fellowship_claims"),
        )
    )
    stmt = await scope.narrow_to_scholars(session, stmt, q, unit_id)
    if state:
        stmt = stmt.where(FellowshipClaim.state == state)
    if scholar_id:
        stmt = stmt.where(FellowshipClaim.scholar_id == scholar_id)
    if fellowship_id:
        stmt = stmt.where(FellowshipClaim.fellowship_id == fellowship_id)
    columns = {
        "month": FellowshipClaim.month,
        "scholar": User.full_name,
        "amount": FellowshipClaim.amount,
        "state": ranked(FellowshipClaim.state, ITEM_STATES),
    }
    default = [FellowshipClaim.month.desc(), User.full_name]
    stmt = ordered(stmt, sort, columns, default, FellowshipClaim.id)
    out = []
    for c, scheme, name in await page_of(session, response, stmt, limit, offset):
        step = c.chain_snapshot[c.current_step]["kind"] if c.current_step is not None else None
        out.append(
            {
                "id": c.id,
                "scholar": {"id": c.scholar_id, "name": name},
                "fellowship_id": c.fellowship_id,
                "scheme": scheme,
                "month": c.month,
                "amount": c.amount,
                "leave_days": c.leave_days,
                "state": c.state,
                "waiting_on": workflow.STEP_LABELS[step] if step else None,
                "submitted_at": c.submitted_at,
                "approved_at": c.approved_at,
            }
        )
    return out


@router.post("", response_model=ItemView, status_code=201)
async def create_claim(
    body: ClaimIn,
    principal: Principal = Depends(require_perm("fellowship_claims", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if principal.scholar_id is None:
        raise ApiError(403, "forbidden", "Scholars claim their own fellowship.")
    fellowship = await session.get(Fellowship, body.fellowship_id)
    if (
        fellowship is None
        or fellowship.deleted_at is not None
        or fellowship.scholar_id != principal.scholar_id
    ):
        raise forbidden()
    grants.check_claim(fellowship, body.month)
    claim = await insert(
        session,
        principal,
        FellowshipClaim(
            scholar_id=principal.scholar_id,
            amount=grants.claim_amount(fellowship),
            **body.model_dump(),
        ),
    )
    await session.commit()
    ctx = await items.load_ctx(session, principal, "fellowship_claim", claim.id)
    return await items.view(session, principal, ctx)


@router.patch("/{claim_id}", response_model=ItemView)
async def update_claim(
    claim_id: uuid.UUID,
    body: ClaimUpdate,
    principal: Principal = Depends(require_perm("fellowship_claims", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Leave days and the note, while the claim is a draft or sent back."""
    ctx = await items.load_ctx(session, principal, "fellowship_claim", claim_id, lock=True)
    workflow.assert_editable(principal, ctx)
    await update(session, principal, ctx.item, body.model_dump(exclude_none=True))
    await session.commit()
    return await items.view(session, principal, ctx)
