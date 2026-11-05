"""Asking a faculty member outside the caller's view to join (PRD F6). The sender types an
email: the directory stays closed, and the reply is the same whether or not it matches. Only
the person asked can accept, and accepting grants that one seminar or scholar, nothing else.
Thesis examiners never go through here: the Exam Office keeps them confidential."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope, seminars
from app.auth.principal import Principal
from app.crud import insert, update
from app.errors import ApiError, forbidden
from app.models import (
    Faculty,
    FacultyRequest,
    OrgUnit,
    Scholar,
    Seminar,
    SeminarPanel,
    Settings,
    User,
)
from app.notify import notify
from app.schemas import FacultyRequestIn

REQUEST_DAYS = 7
REQUEST_LIMIT = 100
LINK = "/requests"


def _is_open(row: FacultyRequest) -> bool:
    return row.status == "pending" and row.expires_at > datetime.now(UTC)


def _status(row: FacultyRequest) -> str:
    return "expired" if row.status == "pending" and not _is_open(row) else row.status


async def _co_supervision_on(session: AsyncSession) -> None:
    if await session.scalar(select(Settings.co_supervision).where(Settings.id == 1)) == "off":
        raise ApiError(
            422, "co_supervision_off", "Co-supervision is switched off for this university."
        )


def _check_scheduled(seminar: Seminar) -> None:
    if seminar.status != "scheduled":
        raise ApiError(422, "seminar_not_scheduled", "This seminar is no longer scheduled.")


async def _authorise_seminar(
    session: AsyncSession, principal: Principal, seminar_id: uuid.UUID
) -> None:
    seminar, path = await seminars.get_seminar(session, principal, seminar_id)
    if not await seminars.may_request_panel(session, principal, seminar.id, path):
        raise forbidden()
    _check_scheduled(seminar)


async def _authorise_scholar(
    session: AsyncSession, principal: Principal, scholar_id: uuid.UUID
) -> None:
    """The scholar's department admin or main supervisor."""
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    path = await scope.unit_path(session, scholar.unit_id)
    is_guide = principal.faculty_id is not None and principal.faculty_id == scholar.supervisor_id
    if not is_guide and not principal.covers("admin", path):
        raise forbidden()
    await _co_supervision_on(session)
    if scholar.co_supervisor_id is not None:
        raise ApiError(409, "co_supervisor_set", "This scholar already has a co-supervisor.")


async def _target_text(session: AsyncSession, row: FacultyRequest) -> str:
    if row.seminar_id:
        title, unit = (
            await session.execute(
                select(Seminar.title, OrgUnit.name)
                .join(OrgUnit, OrgUnit.id == Seminar.unit_id)
                .where(Seminar.id == row.seminar_id)
            )
        ).one()
        return f"Panel of “{title}”, {unit}"
    name, unit = (
        await session.execute(
            select(User.full_name, OrgUnit.name)
            .join(Scholar, Scholar.user_id == User.id)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .where(Scholar.id == row.scholar_id)
        )
    ).one()
    return f"Co-supervisor of {name}, {unit}"


async def _out(session: AsyncSession, row: FacultyRequest) -> dict[str, Any]:
    sender = await session.scalar(select(User.full_name).where(User.id == row.requested_by))
    accepted = None
    if row.status == "accepted":
        accepted = await session.scalar(
            select(User.full_name)
            .join(Faculty, Faculty.user_id == User.id)
            .where(Faculty.id == row.faculty_id)
        )
    return {
        "id": row.id,
        "kind": row.kind,
        "target": await _target_text(session, row),
        "email": row.email,
        "status": _status(row),
        "note": row.note,
        "requested_by_name": sender,
        "faculty_name": accepted,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
    }


async def create(
    session: AsyncSession, principal: Principal, body: FacultyRequestIn
) -> dict[str, Any]:
    if body.seminar_id:
        await _authorise_seminar(session, principal, body.seminar_id)
    else:
        await _authorise_scholar(session, principal, body.scholar_id)
    same = await session.scalars(
        select(FacultyRequest).where(
            FacultyRequest.email == body.email,
            FacultyRequest.seminar_id == body.seminar_id
            if body.seminar_id
            else FacultyRequest.scholar_id == body.scholar_id,
            FacultyRequest.deleted_at.is_(None),
        )
    )
    if any(_is_open(r) for r in same):
        raise ApiError(409, "request_pending", "A request to this address is already waiting.")
    faculty = (
        await session.execute(
            select(Faculty.id, User.id)
            .join(User, User.id == Faculty.user_id)
            .where(
                User.email == body.email,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
                Faculty.deleted_at.is_(None),
            )
        )
    ).first()
    row = await insert(
        session,
        principal,
        FacultyRequest(
            **body.model_dump(),
            faculty_id=faculty[0] if faculty else None,
            requested_by=principal.user_id,
            expires_at=datetime.now(UTC) + timedelta(days=REQUEST_DAYS),
        ),
    )
    if faculty:
        notify(
            session,
            [faculty[1]],
            "system",
            f"{principal.full_name} is asking for your help",
            await _target_text(session, row),
            LINK,
        )
    out = await _out(session, row)
    await session.commit()
    return out


async def listing(session: AsyncSession, principal: Principal) -> dict[str, list[dict[str, Any]]]:
    rows = await session.scalars(
        select(FacultyRequest)
        .where(
            FacultyRequest.deleted_at.is_(None),
            or_(
                FacultyRequest.requested_by == principal.user_id,
                FacultyRequest.faculty_id == principal.faculty_id,
            ),
        )
        .order_by(FacultyRequest.created_at.desc())
        .limit(REQUEST_LIMIT)
    )
    out: dict[str, list[dict[str, Any]]] = {"incoming": [], "sent": []}
    for row in list(rows):
        if row.requested_by == principal.user_id:
            out["sent"].append(await _out(session, row))
        if row.faculty_id == principal.faculty_id and _is_open(row):
            out["incoming"].append(await _out(session, row))
    return out


async def _locked(session: AsyncSession, request_id: uuid.UUID) -> FacultyRequest:
    row = await session.scalar(
        select(FacultyRequest)
        .where(FacultyRequest.id == request_id, FacultyRequest.deleted_at.is_(None))
        .with_for_update()
    )
    if row is None:
        raise forbidden()
    return row


def _require_open(row: FacultyRequest) -> None:
    if not _is_open(row):
        raise ApiError(422, "request_closed", "This request is no longer open.")


async def _join_panel(session: AsyncSession, principal: Principal, row: FacultyRequest) -> None:
    seminar = await session.get(Seminar, row.seminar_id)
    _check_scheduled(seminar)
    seat = await session.scalar(
        select(SeminarPanel).where(
            SeminarPanel.seminar_id == row.seminar_id,
            SeminarPanel.faculty_id == row.faculty_id,
            SeminarPanel.deleted_at.is_(None),
        )
    )
    if seat is None:
        await insert(
            session,
            principal,
            SeminarPanel(seminar_id=row.seminar_id, faculty_id=row.faculty_id),
        )
    else:
        await update(session, principal, seat, {"kind": "panel"})


async def _join_as_co_supervisor(
    session: AsyncSession, principal: Principal, row: FacultyRequest
) -> None:
    await _co_supervision_on(session)
    scholar = await session.get(Scholar, row.scholar_id)
    if scholar.co_supervisor_id is not None:
        raise ApiError(409, "co_supervisor_set", "This scholar already has a co-supervisor.")
    if scholar.supervisor_id == row.faculty_id:
        raise ApiError(
            422,
            "co_supervisor_same_as_supervisor",
            "The co-supervisor must be someone other than the supervisor.",
        )
    await update(session, principal, scholar, {"co_supervisor_id": row.faculty_id})


async def _close(
    session: AsyncSession, principal: Principal, row: FacultyRequest, status: str
) -> dict[str, Any]:
    now = datetime.now(UTC)
    await update(session, principal, row, {"status": status, "responded_at": now})
    if status in ("accepted", "declined"):
        notify(
            session,
            [row.requested_by],
            "system",
            f"{principal.full_name} {status} your request",
            await _target_text(session, row),
            LINK,
        )
    out = await _out(session, row)
    await session.commit()
    return out


async def accept(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID
) -> dict[str, Any]:
    row = await _locked(session, request_id)
    if principal.faculty_id is None or row.faculty_id != principal.faculty_id:
        raise forbidden()
    _require_open(row)
    if row.seminar_id:
        await _join_panel(session, principal, row)
    else:
        await _join_as_co_supervisor(session, principal, row)
    return await _close(session, principal, row, "accepted")


async def decline(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID
) -> dict[str, Any]:
    row = await _locked(session, request_id)
    if principal.faculty_id is None or row.faculty_id != principal.faculty_id:
        raise forbidden()
    _require_open(row)
    return await _close(session, principal, row, "declined")


async def cancel(
    session: AsyncSession, principal: Principal, request_id: uuid.UUID
) -> dict[str, Any]:
    row = await _locked(session, request_id)
    if row.requested_by != principal.user_id:
        raise forbidden()
    _require_open(row)
    return await _close(session, principal, row, "cancelled")
