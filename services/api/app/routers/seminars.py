"""Progress seminars: schedule, edit, cancel, hardcopy (PRD F15, UX Flow 6b)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import grading, scope, seminars
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.errors import ApiError
from app.models import (
    Faculty,
    OrgUnit,
    ProgressReport,
    Scholar,
    Seminar,
    SeminarPanel,
    SeminarScholar,
    Settings,
    User,
)
from app.notify import notify
from app.schemas import HardcopyIn, SeminarDetail, SeminarIn, SeminarRow, SeminarUpdate

router = APIRouter(prefix="/seminars", tags=["seminars"])

SupFaculty = aliased(Faculty)
SupUser = aliased(User)


def _row(s: Seminar, unit_name: str, scholar_count: int) -> dict[str, Any]:
    return {
        "id": s.id,
        "unit": {"id": s.unit_id, "name": unit_name},
        "title": s.title,
        "starts_at": s.starts_at,
        "venue": s.venue,
        "report_due": s.report_due,
        "report_year": s.report_year,
        "period": s.period,
        "status": s.status,
        "scholar_count": scholar_count,
    }


@router.get("", response_model=list[SeminarRow])
async def list_seminars(
    upcoming: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    count = (
        select(func.count())
        .select_from(SeminarScholar)
        .where(SeminarScholar.seminar_id == Seminar.id, SeminarScholar.deleted_at.is_(None))
        .correlate(Seminar)
        .scalar_subquery()
    )
    stmt = (
        select(Seminar, OrgUnit.name, count)
        .join(OrgUnit, OrgUnit.id == Seminar.unit_id)
        .where(
            Seminar.deleted_at.is_(None),
            seminars.visible(principal, await seminars.open_to_faculty(session)),
        )
    )
    if upcoming:
        stmt = stmt.where(Seminar.starts_at >= datetime.now(UTC), Seminar.status == "scheduled")
    rows = await session.execute(
        stmt.order_by(Seminar.starts_at.asc() if upcoming else Seminar.starts_at.desc()).limit(
            limit
        )
    )
    return [_row(s, name, n) for s, name, n in rows]


async def _detail(
    session: AsyncSession, principal: Principal, seminar_id: uuid.UUID
) -> dict[str, Any]:
    seminar, path = await seminars.get_seminar(session, principal, seminar_id)
    unit_name = await session.scalar(select(OrgUnit.name).where(OrgUnit.id == seminar.unit_id))
    settings = await session.get(Settings, 1)
    is_grader = await grading.is_grader(session, principal, seminar.id)
    scholar_rows = await session.execute(
        select(SeminarScholar, Scholar, User.full_name, SupUser.full_name, ProgressReport.state)
        .join(Scholar, Scholar.id == SeminarScholar.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .outerjoin(SupFaculty, SupFaculty.id == Scholar.supervisor_id)
        .outerjoin(SupUser, SupUser.id == SupFaculty.user_id)
        .outerjoin(
            ProgressReport,
            (ProgressReport.scholar_id == Scholar.id)
            & (ProgressReport.report_year == seminar.report_year)
            & (ProgressReport.period == seminar.period)
            & ProgressReport.deleted_at.is_(None),
        )
        .where(SeminarScholar.seminar_id == seminar.id, SeminarScholar.deleted_at.is_(None))
        .order_by(User.full_name)
    )
    panel_rows = await session.execute(
        select(SeminarPanel, User.full_name)
        .join(Faculty, Faculty.id == SeminarPanel.faculty_id)
        .join(User, User.id == Faculty.user_id)
        .where(SeminarPanel.seminar_id == seminar.id, SeminarPanel.deleted_at.is_(None))
        .order_by(User.full_name)
    )
    return {
        **_row(seminar, unit_name or "", 0),
        "notes": seminar.notes,
        "scholars": [
            {
                "scholar": {"id": sc.id, "name": name},
                "roll_number": sc.roll_number,
                "supervisor": sup_name,
                "report_state": state,
                "hardcopy_received_on": ss.hardcopy_received_on,
                "finalised_at": ss.finalised_at,
            }
            for ss, sc, name, sup_name, state in scholar_rows
        ],
        "panel": [
            {"faculty_id": p.faculty_id, "name": name, "kind": p.kind} for p, name in panel_rows
        ],
        "can_manage": seminars.can_manage(principal, path),
        "require_hardcopy": settings.require_hardcopy if settings else False,
        "is_grader": is_grader,
        "can_attend": (
            principal.faculty_id is not None
            and not is_grader
            and seminar.status == "scheduled"
            and settings is not None
            and settings.seminar_graders == "panel_and_attending"
        ),
    }


@router.get("/{seminar_id}", response_model=SeminarDetail)
async def get_seminar(
    seminar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _detail(session, principal, seminar_id)


async def _set_members(
    session: AsyncSession,
    principal: Principal,
    seminar: Seminar,
    scholar_ids: list[uuid.UUID] | None,
    panel_ids: list[uuid.UUID] | None,
) -> None:
    """Replace the scholar list / panel: soft-delete removed rows, insert new ones."""
    if scholar_ids is not None:
        current = {
            r.scholar_id: r
            for r in await session.scalars(
                select(SeminarScholar).where(
                    SeminarScholar.seminar_id == seminar.id, SeminarScholar.deleted_at.is_(None)
                )
            )
        }
        for sid, row in current.items():
            if sid not in scholar_ids:
                await soft_delete(session, principal, row)
        for sid in dict.fromkeys(scholar_ids):
            if sid not in current:
                await insert(
                    session, principal, SeminarScholar(seminar_id=seminar.id, scholar_id=sid)
                )
    if panel_ids is not None:
        current_panel = {
            r.faculty_id: r
            for r in await session.scalars(
                select(SeminarPanel).where(
                    SeminarPanel.seminar_id == seminar.id,
                    SeminarPanel.deleted_at.is_(None),
                    SeminarPanel.kind == "panel",
                )
            )
        }
        for fid, row in current_panel.items():
            if fid not in panel_ids:
                await soft_delete(session, principal, row)
        for fid in dict.fromkeys(panel_ids):
            if fid not in current_panel:
                await insert(
                    session, principal, SeminarPanel(seminar_id=seminar.id, faculty_id=fid)
                )


async def _announce(session: AsyncSession, seminar: Seminar, path: str, verb: str) -> None:
    when = seminar.starts_at.astimezone().strftime("%d %b %Y, %H:%M")
    venue = seminar.venue or "venue to be announced"
    body = f"{when} · {venue} · report due {seminar.report_due:%d %b %Y}"
    notify(
        session,
        await seminars.recipients(session, seminar, path),
        "seminar",
        f"Progress seminar {verb}: {seminar.title}",
        body,
        f"/seminars/{seminar.id}",
    )


@router.post("", response_model=SeminarDetail, status_code=201)
async def schedule(
    body: SeminarIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    path = await scope.unit_path(session, body.unit_id)
    seminars.require_manager(principal, path)
    await seminars.check_scholars_in_unit(session, path, body.scholar_ids)
    await seminars.check_faculty(session, body.panel_faculty_ids)
    seminar = await insert(
        session,
        principal,
        Seminar(
            unit_id=body.unit_id,
            title=body.title,
            starts_at=body.starts_at,
            venue=body.venue,
            report_due=body.report_due,
            report_year=body.report_year,
            period=body.period,
            notes=body.notes,
            created_by=principal.user_id,
        ),
    )
    await _set_members(session, principal, seminar, body.scholar_ids, body.panel_faculty_ids)
    await session.flush()
    await _announce(session, seminar, path, "scheduled")
    await session.commit()
    return await _detail(session, principal, seminar.id)


@router.patch("/{seminar_id}", response_model=SeminarDetail)
async def edit(
    seminar_id: uuid.UUID,
    body: SeminarUpdate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    seminar, path = await seminars.get_seminar(session, principal, seminar_id)
    seminars.require_manager(principal, path)
    if seminar.status == "cancelled":
        raise ApiError(422, "seminar_cancelled", "A cancelled seminar cannot be changed.")
    changes = body.model_dump(exclude_unset=True, exclude={"scholar_ids", "panel_faculty_ids"})
    if body.scholar_ids is not None:
        await seminars.check_scholars_in_unit(session, path, body.scholar_ids)
    if body.panel_faculty_ids is not None:
        await seminars.check_faculty(session, body.panel_faculty_ids)
    await update(session, principal, seminar, changes)
    await _set_members(session, principal, seminar, body.scholar_ids, body.panel_faculty_ids)
    await session.flush()
    await _announce(session, seminar, path, "updated")
    await session.commit()
    return await _detail(session, principal, seminar_id)


@router.post("/{seminar_id}/cancel", response_model=SeminarDetail)
async def cancel(
    seminar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    seminar, path = await seminars.get_seminar(session, principal, seminar_id)
    seminars.require_manager(principal, path)
    if seminar.status != "cancelled":
        await update(session, principal, seminar, {"status": "cancelled"})
        await _announce(session, seminar, path, "cancelled")
        await session.commit()
    return await _detail(session, principal, seminar_id)


@router.put("/{seminar_id}/hardcopy/{scholar_id}", response_model=SeminarDetail)
async def set_hardcopy(
    seminar_id: uuid.UUID,
    scholar_id: uuid.UUID,
    body: HardcopyIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    seminar, path = await seminars.get_seminar(session, principal, seminar_id)
    seminars.require_manager(principal, path)
    settings = await session.get(Settings, 1)
    if not (settings and settings.require_hardcopy):
        raise ApiError(422, "hardcopy_not_required", "This university does not require hardcopies.")
    row = await session.scalar(
        select(SeminarScholar).where(
            SeminarScholar.seminar_id == seminar.id,
            SeminarScholar.scholar_id == scholar_id,
            SeminarScholar.deleted_at.is_(None),
        )
    )
    if row is None:
        raise ApiError(422, "not_in_seminar", "This scholar is not part of the seminar.")
    await update(session, principal, row, {"hardcopy_received_on": body.received_on})
    await session.commit()
    return await _detail(session, principal, seminar_id)
