"""Supervisor and co-supervisor appointments, kept as history (PRD F17, Form IV). The scholar's
`supervisor_id` / `co_supervisor_id` name who guides them now; `supervisor_appointments` keeps
every appointment, past and present. Both change only here, so they never disagree."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.crud import insert, update
from app.models import Faculty, Scholar, SupervisorAppointment, User

COLUMN = {"supervisor": "supervisor_id", "co_supervisor": "co_supervisor_id"}


async def current(
    session: AsyncSession, scholar_id: uuid.UUID, role: str
) -> SupervisorAppointment | None:
    return await session.scalar(
        select(SupervisorAppointment).where(
            SupervisorAppointment.scholar_id == scholar_id,
            SupervisorAppointment.role == role,
            SupervisorAppointment.ended_on.is_(None),
            SupervisorAppointment.deleted_at.is_(None),
        )
    )


async def change(
    session: AsyncSession,
    principal: Principal | None,
    scholar: Scholar,
    role: str,
    faculty_id: uuid.UUID | None,
    *,
    on: date | None = None,
    order_ref: str | None = None,
) -> None:
    """Make `faculty_id` the scholar's supervisor (or co-supervisor), or nobody: the current
    appointment ends `on` (today if not given) and a new one opens, with the order behind it
    when known (an approved change of supervisor). Checks of who may be appointed are the
    caller's."""
    if getattr(scholar, COLUMN[role]) == faculty_id:
        return
    day = on or datetime.now(UTC).date()
    open_row = await current(session, scholar.id, role)
    if open_row is not None:
        await update(session, principal, open_row, {"ended_on": day})
    await update(session, principal, scholar, {COLUMN[role]: faculty_id})
    if faculty_id is not None:
        await insert(
            session,
            principal,
            SupervisorAppointment(
                scholar_id=scholar.id,
                faculty_id=faculty_id,
                role=role,
                appointed_on=on,
                order_ref=order_ref,
            ),
        )


async def history(
    session: AsyncSession, scholar_id: uuid.UUID, *, with_co: bool
) -> list[dict[str, Any]]:
    """Every appointment, the current ones first, then the latest ended first."""
    rows = await session.execute(
        select(SupervisorAppointment, User.full_name)
        .join(Faculty, Faculty.id == SupervisorAppointment.faculty_id)
        .join(User, User.id == Faculty.user_id)
        .where(
            SupervisorAppointment.scholar_id == scholar_id,
            SupervisorAppointment.deleted_at.is_(None),
        )
    )
    out = [
        {
            "id": a.id,
            "role": a.role,
            "faculty": {"id": a.faculty_id, "name": name},
            "appointed_on": a.appointed_on,
            "order_ref": a.order_ref,
            "ended_on": a.ended_on,
            "since": a.created_at,
        }
        for a, name in rows
        if with_co or a.role == "supervisor"
    ]
    out.sort(key=lambda a: (a["ended_on"] is not None, -a["since"].timestamp()))
    return out
