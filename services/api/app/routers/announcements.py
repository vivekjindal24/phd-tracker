"""The notice board (announcements.py): read what you may, post where you may."""

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import announcements, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import LOCAL_TZ
from app.models import Announcement, OrgUnit, User
from app.notify import notify
from app.schemas import NoticeBoardIn, NoticeBoardUpdate

router = APIRouter(prefix="/announcements", tags=["notice board"])


def _today() -> date:
    return datetime.now(LOCAL_TZ).date()


async def _out(session: AsyncSession, principal: Principal, rows: list[Announcement]) -> list:
    units = dict(
        (
            await session.execute(
                select(OrgUnit.id, OrgUnit.name).where(
                    OrgUnit.id.in_([r.unit_id for r in rows if r.unit_id])
                )
            )
        ).all()
    )
    names = dict(
        (
            await session.execute(
                select(User.id, User.full_name).where(User.id.in_([r.posted_by for r in rows]))
            )
        ).all()
    )
    out = []
    for r in rows:
        path = await announcements.path_of(session, r)
        out.append(
            {
                "id": r.id,
                "unit": {"id": r.unit_id, "name": units.get(r.unit_id)} if r.unit_id else None,
                "title": r.title,
                "body": r.body,
                "pinned": r.pinned,
                "ends_on": r.ends_on,
                "posted_by": names.get(r.posted_by),
                "posted_at": r.created_at,
                "can_manage": announcements.may_post(principal, path),
            }
        )
    return out


@router.get("")
async def board(
    past: bool = False,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """The notices the caller reads: current ones, pinned first, newest next; or past ones."""
    today = _today()
    when = ~announcements.current(today) if past else announcements.current(today)
    rows = await session.scalars(
        select(Announcement)
        .where(Announcement.deleted_at.is_(None), announcements.visible(principal), when)
        .order_by(Announcement.pinned.desc(), Announcement.created_at.desc())
        .limit(200)
    )
    return await _out(session, principal, list(rows))


@router.get("/where")
async def where_to_post(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Where the caller may post: the whole university, and which units."""
    everywhere = announcements.may_post(principal, None)
    query = select(OrgUnit.id, OrgUnit.name).where(OrgUnit.deleted_at.is_(None))
    if not everywhere:
        paths = tuple(r.unit_path for r in principal.unit_roles if r.role == "admin")
        if not paths:
            return {"university": False, "units": []}
        query = query.where(OrgUnit.id.in_(scope.subtree_unit_ids(paths)))
    rows = await session.execute(query.order_by(OrgUnit.path))
    return {"university": everywhere, "units": [{"id": i, "name": n} for i, n in rows]}


@router.post("", status_code=201)
async def post(
    body: NoticeBoardIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    path = await scope.unit_path(session, body.unit_id) if body.unit_id else None
    announcements.require_post(principal, path)
    row = await insert(
        session, principal, Announcement(**body.model_dump(), posted_by=principal.user_id)
    )
    notify(
        session,
        await announcements.recipients(session, path),
        "notice",
        f"Notice: {row.title}",
        row.body[:300],
        "/notices",
    )
    await session.commit()
    (out,) = await _out(session, principal, [row])
    return out


@router.patch("/{notice_id}")
async def edit(
    notice_id: uuid.UUID,
    body: NoticeBoardUpdate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await announcements.get_or_403(session, principal, notice_id)
    announcements.require_post(principal, await announcements.path_of(session, row))
    await update(session, principal, row, body.model_dump(exclude_unset=True))
    await session.commit()
    (out,) = await _out(session, principal, [row])
    return out


@router.delete("/{notice_id}", status_code=204)
async def remove(
    notice_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await announcements.get_or_403(session, principal, notice_id)
    announcements.require_post(principal, await announcements.path_of(session, row))
    await soft_delete(session, principal, row)
    await session.commit()
