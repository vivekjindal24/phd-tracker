"""Faculty directory (PRD F6): readable by every role — a university's faculty list is public
inside it. Edits need an admin over the faculty member's unit."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import directory, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import DESIGNATIONS, UGC_CAP
from app.errors import ApiError, forbidden
from app.models import Faculty, OrgUnit, SupervisorStandIn, User
from app.notify import notify
from app.rbac import require_perm
from app.schemas import (
    FacultyOut,
    FacultyUpdate,
    Ref,
    StandInFor,
    StandInIn,
    StandInOut,
    StandIns,
)
from app.sorting import Sort, ordered, page_of, ranked

router = APIRouter(prefix="/faculty", tags=["directory"])

_load = directory.load_of_faculty()


def _query() -> Select:
    return (
        select(Faculty, User.full_name, User.email, OrgUnit.name, _load)
        .join(User, User.id == Faculty.user_id)
        .join(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .where(Faculty.deleted_at.is_(None))
    )


def _out(row) -> FacultyOut:
    f, name, email, unit_name, load = row
    return FacultyOut(
        id=f.id,
        user_id=f.user_id,
        full_name=name,
        email=email,
        unit=Ref(id=f.unit_id, name=unit_name),
        designation=f.designation,
        employee_id=f.employee_id,
        can_supervise=f.can_supervise,
        max_scholars=f.max_scholars,
        load=load,
    )


@router.get("", response_model=list[FacultyOut])
async def list_faculty(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    can_supervise: bool | None = None,
    with_capacity: bool = False,
    sort: Sort = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[FacultyOut]:
    stmt = _query().where(scope.faculty_predicate(principal))
    if q:
        stmt = stmt.where(User.full_name.icontains(q, autoescape=True))
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Faculty.unit_id.in_(scope.subtree_unit_ids((path,))))
    if can_supervise is not None:
        stmt = stmt.where(Faculty.can_supervise.is_(can_supervise))
    if with_capacity:  # supervisor pickers list only people below their cap
        stmt = stmt.where(_load < Faculty.max_scholars)
    columns = {
        "name": User.full_name,
        "designation": ranked(Faculty.designation, DESIGNATIONS),
        "department": OrgUnit.name,
        "load": _load,
    }
    stmt = ordered(stmt, sort, columns, [User.full_name], Faculty.id)
    rows = await page_of(session, response, stmt, limit, offset)
    return [_out(r) for r in rows]


MAX_STAND_IN_DAYS = 180
StandInFaculty = aliased(Faculty)
StandInUser = aliased(User)


async def _stand_ins(session: AsyncSession, principal: Principal) -> StandIns:
    today = datetime.now(UTC).date()
    live = (SupervisorStandIn.deleted_at.is_(None), SupervisorStandIn.ends_on >= today)
    mine = (
        await session.execute(
            select(SupervisorStandIn, StandInFaculty.id, StandInUser.full_name)
            .join(StandInFaculty, StandInFaculty.id == SupervisorStandIn.stand_in_id)
            .join(StandInUser, StandInUser.id == StandInFaculty.user_id)
            .where(SupervisorStandIn.faculty_id == principal.faculty_id, *live)
        )
    ).first()
    others = await session.execute(
        select(SupervisorStandIn, Faculty.id, User.full_name)
        .join(Faculty, Faculty.id == SupervisorStandIn.faculty_id)
        .join(User, User.id == Faculty.user_id)
        .where(SupervisorStandIn.stand_in_id == principal.faculty_id, *live)
        .order_by(SupervisorStandIn.starts_on)
    )
    return StandIns(
        mine=StandInOut(
            stand_in=Ref(id=mine[1], name=mine[2]),
            starts_on=mine[0].starts_on,
            ends_on=mine[0].ends_on,
        )
        if mine
        else None,
        standing_in_for=[
            StandInFor(supervisor=Ref(id=fid, name=name), starts_on=s.starts_on, ends_on=s.ends_on)
            for s, fid, name in others
        ],
    )


async def _end_stand_in(session: AsyncSession, principal: Principal) -> None:
    current = await session.scalar(
        select(SupervisorStandIn).where(
            SupervisorStandIn.faculty_id == principal.faculty_id,
            SupervisorStandIn.deleted_at.is_(None),
        )
    )
    if current is not None:
        await soft_delete(session, principal, current)


def _colleagues(principal: Principal) -> Select:
    """Who a supervisor may name: the other supervisors of their own department. Their names
    are listed for this choice even where the wider faculty directory is not open to them."""
    own_unit = select(Faculty.unit_id).where(Faculty.id == principal.faculty_id).scalar_subquery()
    return select(Faculty).where(
        Faculty.deleted_at.is_(None),
        Faculty.unit_id == own_unit,
        Faculty.id != principal.faculty_id,
        Faculty.can_supervise.is_(True),
    )


@router.get("/me/stand-in/candidates", response_model=list[Ref])
async def stand_in_candidates(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Ref]:
    if principal.faculty_id is None or not principal.can_supervise:
        raise forbidden()
    rows = await session.execute(
        _colleagues(principal)
        .join(User, User.id == Faculty.user_id)
        .with_only_columns(Faculty.id, User.full_name)
        .order_by(User.full_name)
    )
    return [Ref(id=fid, name=name) for fid, name in rows]


@router.get("/me/stand-in", response_model=StandIns)
async def get_stand_in(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> StandIns:
    if principal.faculty_id is None:
        raise forbidden()
    return await _stand_ins(session, principal)


@router.put("/me/stand-in", response_model=StandIns)
async def set_stand_in(
    body: StandInIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> StandIns:
    """A supervisor names the colleague who acts at the supervisor step for their scholars
    between two dates (PRD F3). Replaces any stand-in they had."""
    if principal.faculty_id is None or not principal.can_supervise:
        raise forbidden()
    today = datetime.now(UTC).date()
    if body.ends_on < max(body.starts_on, today):
        raise ApiError(
            422, "invalid_dates", "The end date must be today or later, and not before the start."
        )
    if (body.ends_on - body.starts_on).days > MAX_STAND_IN_DAYS:
        raise ApiError(422, "invalid_dates", f"A stand-in lasts at most {MAX_STAND_IN_DAYS} days.")
    stand_in = await session.scalar(_colleagues(principal).where(Faculty.id == body.stand_in_id))
    if stand_in is None:
        raise ApiError(422, "invalid_stand_in", "Choose a supervisor from your own department.")
    await _end_stand_in(session, principal)
    await session.flush()
    await insert(
        session,
        principal,
        SupervisorStandIn(
            faculty_id=principal.faculty_id,
            stand_in_id=stand_in.id,
            starts_on=body.starts_on,
            ends_on=body.ends_on,
        ),
    )
    notify(
        session,
        [stand_in.user_id],
        "approval_waiting",
        f"You are {principal.full_name}'s stand-in",
        f"From {body.starts_on:%d %b %Y} to {body.ends_on:%d %b %Y} you can approve or send "
        "back items waiting at their supervisor step. They appear in your queue.",
        "/queue",
    )
    await session.commit()
    return await _stand_ins(session, principal)


@router.delete("/me/stand-in", response_model=StandIns)
async def remove_stand_in(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> StandIns:
    if principal.faculty_id is None:
        raise forbidden()
    await _end_stand_in(session, principal)
    await session.commit()
    return await _stand_ins(session, principal)


@router.get("/{faculty_id}", response_model=FacultyOut)
async def get_faculty(
    faculty_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> FacultyOut:
    stmt = _query().where(Faculty.id == faculty_id, scope.faculty_predicate(principal))
    row = (await session.execute(stmt)).first()
    if row is None:
        raise forbidden()
    return _out(row)


@router.patch("/{faculty_id}", response_model=FacultyOut)
async def update_faculty(
    faculty_id: uuid.UUID,
    body: FacultyUpdate,
    principal: Principal = Depends(require_perm("faculty", "update")),
    session: AsyncSession = Depends(get_session),
) -> FacultyOut:
    faculty = await session.scalar(
        select(Faculty).where(Faculty.id == faculty_id, Faculty.deleted_at.is_(None))
    )
    if faculty is None:
        raise forbidden()
    scope.require_admin_over(principal, await scope.unit_path(session, faculty.unit_id))
    changes = body.model_dump(exclude_unset=True)
    if "unit_id" in changes:
        scope.require_admin_over(principal, await scope.unit_path(session, changes["unit_id"]))
    designation = changes.get("designation", faculty.designation)
    max_scholars = changes.get("max_scholars", faculty.max_scholars)
    if "designation" in changes and "max_scholars" not in changes:
        max_scholars = changes["max_scholars"] = UGC_CAP[designation]  # same default as create
    directory.validate_faculty_cap(designation, max_scholars)
    await update(session, principal, faculty, changes)
    await session.commit()
    return await get_faculty(faculty_id, principal, session)
