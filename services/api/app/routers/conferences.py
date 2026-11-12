"""Conferences & talks (PRD M2): recorded by the scholar, visible upward; no chain."""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import CONFERENCE_TYPES
from app.errors import ApiError, forbidden
from app.models import Conference, Scholar, User
from app.modules import require_module
from app.rbac import require_perm
from app.schemas import Ref
from app.schemas.research import ConferenceIn, ConferenceOut, ConferenceUpdate
from app.sorting import Sort, ordered, page_of, ranked

router = APIRouter(
    prefix="/conferences",
    tags=["conferences"],
    dependencies=[Depends(require_module("conferences"))],
)


def _query(principal: Principal) -> Select:
    return (
        select(Conference, Scholar.id, User.full_name)
        .join(Scholar, Scholar.id == Conference.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .where(
            Conference.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "conferences"),
        )
    )


def _out(row, principal: Principal) -> ConferenceOut:
    c, sid, name = row
    return ConferenceOut(
        id=c.id,
        scholar=Ref(id=sid, name=name),
        event_name=c.event_name,
        event_type=c.event_type,
        event_date=c.event_date,
        place=c.place,
        title=c.title,
        can_edit=sid == principal.scholar_id,
    )


async def _own(session: AsyncSession, principal: Principal, conference_id: uuid.UUID):
    row = (await session.execute(_query(principal).where(Conference.id == conference_id))).first()
    if row is None or row[1] != principal.scholar_id:
        raise forbidden()
    return row


@router.get("", response_model=list[ConferenceOut])
async def list_conferences(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    scholar_id: uuid.UUID | None = None,
    sort: Sort = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_perm("conferences", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[ConferenceOut]:
    stmt = await scope.narrow_to_scholars(
        session, _query(principal), q, unit_id, Conference.title, Conference.event_name
    )
    if scholar_id:
        stmt = stmt.where(Conference.scholar_id == scholar_id)
    columns = {
        "date": Conference.event_date,
        "event": Conference.event_name,
        "scholar": User.full_name,
        "contribution": ranked(Conference.event_type, CONFERENCE_TYPES),
    }
    stmt = ordered(stmt, sort, columns, [Conference.event_date.desc()], Conference.id)
    rows = await page_of(session, response, stmt, limit, offset)
    return [_out(r, principal) for r in rows]


@router.post("", response_model=ConferenceOut, status_code=201)
async def create_conference(
    body: ConferenceIn,
    principal: Principal = Depends(require_perm("conferences", "create")),
    session: AsyncSession = Depends(get_session),
) -> ConferenceOut:
    if principal.scholar_id is None:
        raise ApiError(403, "forbidden", "Scholars record their own conferences.")
    c = await insert(
        session, principal, Conference(scholar_id=principal.scholar_id, **body.model_dump())
    )
    await session.commit()
    return _out(await _own(session, principal, c.id), principal)


@router.patch("/{conference_id}", response_model=ConferenceOut)
async def update_conference(
    conference_id: uuid.UUID,
    body: ConferenceUpdate,
    principal: Principal = Depends(require_perm("conferences", "update")),
    session: AsyncSession = Depends(get_session),
) -> ConferenceOut:
    c, *_ = await _own(session, principal, conference_id)
    await update(session, principal, c, body.model_dump(exclude_unset=True))
    await session.commit()
    return _out(await _own(session, principal, conference_id), principal)


@router.delete("/{conference_id}", status_code=204)
async def delete_conference(
    conference_id: uuid.UUID,
    principal: Principal = Depends(require_perm("conferences", "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    c, *_ = await _own(session, principal, conference_id)
    await soft_delete(session, principal, c)
    await session.commit()
