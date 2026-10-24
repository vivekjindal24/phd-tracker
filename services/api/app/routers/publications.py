"""Publications (PRD M1, UX Flow 7): written by the scholar, verified by the Library at its
step, through the publication approval chain. Workflow actions live on /items."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, scope, workflow
from app.auth.principal import Principal
from app.crud import insert, update
from app.db import get_session
from app.enums import ItemState
from app.errors import ApiError
from app.models import Publication, Scholar, User
from app.modules import require_module
from app.rbac import require_perm
from app.schemas import ItemView
from app.schemas.research import PublicationIn, PublicationRow, PublicationUpdate, VerificationIn

router = APIRouter(
    prefix="/publications",
    tags=["publications"],
    dependencies=[Depends(require_module("publications"))],
)


@router.get("", response_model=list[PublicationRow])
async def list_publications(
    state: ItemState | None = None,
    scholar_id: uuid.UUID | None = None,
    pub_year: int | None = Query(default=None, ge=1950, le=2100),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_perm("publications", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(Publication, Scholar.id, User.full_name)
        .join(Scholar, Scholar.id == Publication.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .where(
            Publication.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "publications"),
        )
    )
    if state:
        stmt = stmt.where(Publication.state == state)
    if scholar_id:
        stmt = stmt.where(Publication.scholar_id == scholar_id)
    if pub_year:
        stmt = stmt.where(Publication.pub_year == pub_year)
    rows = await session.execute(
        stmt.order_by(Publication.pub_year.desc(), Publication.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    out = []
    for p, sid, name in rows:
        step = p.chain_snapshot[p.current_step]["kind"] if p.current_step is not None else None
        out.append(
            {
                "id": p.id,
                "scholar": {"id": sid, "name": name},
                "title": p.title,
                "venue": p.venue,
                "pub_type": p.pub_type,
                "pub_year": p.pub_year,
                "indexing": list(p.indexing),
                "state": p.state,
                "waiting_on": workflow.STEP_LABELS[step] if step else None,
                "updated_at": p.updated_at,
            }
        )
    return out


@router.post("", response_model=ItemView, status_code=201)
async def create_publication(
    body: PublicationIn,
    principal: Principal = Depends(require_perm("publications", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if principal.scholar_id is None:
        raise ApiError(403, "forbidden", "Scholars record their own publications.")
    pub = await insert(
        session, principal, Publication(scholar_id=principal.scholar_id, **body.model_dump())
    )
    await session.commit()
    ctx = await items.load_ctx(session, principal, "publication", pub.id)
    return await items.view(session, principal, ctx)


@router.patch("/{publication_id}", response_model=ItemView)
async def update_publication(
    publication_id: uuid.UUID,
    body: PublicationUpdate,
    principal: Principal = Depends(require_perm("publications", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await items.load_ctx(session, principal, "publication", publication_id, lock=True)
    workflow.assert_editable(principal, ctx)
    await update(session, principal, ctx.item, body.model_dump(exclude_unset=True))
    await session.commit()
    return await items.view(session, principal, ctx)


@router.put("/{publication_id}/verification", response_model=ItemView)
async def verify_publication(
    publication_id: uuid.UUID,
    body: VerificationIn,
    principal: Principal = Depends(require_perm("publications", "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The Library corrects indexing and DOI to what it verified, then approves (PRD M1)."""
    ctx = await items.load_ctx(session, principal, "publication", publication_id, lock=True)
    await workflow.assert_step_field(session, principal, ctx, "library")
    await update(session, principal, ctx.item, body.model_dump())
    await session.commit()
    return await items.view(session, principal, ctx)
