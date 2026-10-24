"""Coursework (PRD M4, UX Flow 9): the catalogue (admins over the unit, or the Exam Office),
enrolments and grades (Exam Office), and the clearance the Exam Office starts — its chain runs
on /items and refuses a record that breaks the credit / CGPA minimums (coursework.py)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import coursework, items, scope, workflow
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.errors import ApiError, forbidden
from app.models import Course, CourseworkClearance, Enrolment, OrgUnit, Scholar, User
from app.modules import require_module
from app.rbac import require_perm
from app.schemas import (
    ClearanceIn,
    CourseIn,
    CourseOut,
    CourseUpdate,
    CourseworkView,
    EnrolmentIn,
    EnrolmentUpdate,
    ItemView,
)

router = APIRouter(tags=["coursework"], dependencies=[Depends(require_module("coursework"))])


def _course(c: Course, unit_name: str) -> dict[str, Any]:
    return {
        "id": c.id,
        "unit": {"id": c.unit_id, "name": unit_name},
        "code": c.code,
        "title": c.title,
        "credits": c.credits,
    }


async def _require_catalogue_writer(
    session: AsyncSession, principal: Principal, unit_id: uuid.UUID
) -> None:
    if "exam_office" in principal.office_roles:
        return
    scope.require_admin_over(principal, await scope.unit_path(session, unit_id))


@router.get("/courses", response_model=list[CourseOut])
async def list_courses(
    unit_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    _: Principal = Depends(require_perm("courses", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(Course, OrgUnit.name)
        .join(OrgUnit, OrgUnit.id == Course.unit_id)
        .where(Course.deleted_at.is_(None))
    )
    if unit_id:
        stmt = stmt.where(Course.unit_id == unit_id)
    rows = await session.execute(stmt.order_by(OrgUnit.name, Course.code).limit(limit))
    return [_course(c, name) for c, name in rows]


@router.post("/courses", response_model=CourseOut, status_code=201)
async def create_course(
    body: CourseIn,
    principal: Principal = Depends(require_perm("courses", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_catalogue_writer(session, principal, body.unit_id)
    c = await insert(session, principal, Course(**body.model_dump()))
    await session.commit()
    return _course(c, await session.scalar(select(OrgUnit.name).where(OrgUnit.id == c.unit_id)))


async def _live_course(session: AsyncSession, course_id: uuid.UUID) -> Course:
    c = await session.scalar(
        select(Course).where(Course.id == course_id, Course.deleted_at.is_(None))
    )
    if c is None:
        raise ApiError(422, "course_not_found", "This course does not exist.")
    return c


@router.patch("/courses/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: uuid.UUID,
    body: CourseUpdate,
    principal: Principal = Depends(require_perm("courses", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    c = await _live_course(session, course_id)
    await _require_catalogue_writer(session, principal, c.unit_id)
    await update(session, principal, c, body.model_dump(exclude_unset=True))
    await session.commit()
    return _course(c, await session.scalar(select(OrgUnit.name).where(OrgUnit.id == c.unit_id)))


@router.delete("/courses/{course_id}", status_code=204)
async def delete_course(
    course_id: uuid.UUID,
    principal: Principal = Depends(require_perm("courses", "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    c = await _live_course(session, course_id)
    await _require_catalogue_writer(session, principal, c.unit_id)
    used = await session.scalar(
        select(exists().where(Enrolment.course_id == course_id, Enrolment.deleted_at.is_(None)))
    )
    if used:
        raise ApiError(422, "course_in_use", "Scholars are enrolled in this course.")
    await soft_delete(session, principal, c)
    await session.commit()


async def _view(session: AsyncSession, principal: Principal, scholar: Scholar) -> dict[str, Any]:
    s = await coursework.summary(session, scholar.id)
    unit_names = dict(
        (
            await session.execute(
                select(OrgUnit.id, OrgUnit.name).where(
                    OrgUnit.id.in_({c.unit_id for _, c in s["rows"]})
                )
            )
        ).all()
    )
    clearance = await coursework.clearance(session, scholar.id)
    ref = None
    if clearance is not None:
        step = (
            clearance.chain_snapshot[clearance.current_step]["kind"]
            if clearance.current_step is not None
            else None
        )
        ref = {
            "id": clearance.id,
            "state": clearance.state,
            "waiting_on": workflow.STEP_LABELS[step] if step else None,
            "cleared_on": clearance.cleared_on,
        }
    name = await session.scalar(select(User.full_name).where(User.id == scholar.user_id))
    return {
        "scholar": {"id": scholar.id, "name": name},
        "enrolments": [
            {
                "id": e.id,
                "course": _course(c, unit_names[c.unit_id]),
                "semester": e.semester,
                "grade": e.grade,
                "grade_points": e.grade_points,
            }
            for e, c in s["rows"]
        ],
        "credits": s["credits"],
        "cgpa": s["cgpa"],
        "min_credits": s["min_credits"],
        "min_cgpa": s["min_cgpa"],
        "problems": s["problems"],
        "clearance": ref,
        "can_manage": "exam_office" in principal.office_roles,
        "locked": clearance is not None and clearance.state in coursework.LOCKED_STATES,
    }


@router.get("/scholars/{scholar_id}/coursework", response_model=CourseworkView)
async def get_coursework(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(require_perm("enrolments", "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, "enrolments")
    return await _view(session, principal, scholar)


@router.post("/enrolments", response_model=CourseworkView, status_code=201)
async def enrol(
    body: EnrolmentIn,
    principal: Principal = Depends(require_perm("enrolments", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, body.scholar_id, "enrolments")
    await coursework.require_unlocked(session, scholar.id)
    await _live_course(session, body.course_id)
    await insert(session, principal, Enrolment(**body.model_dump()))
    await session.commit()
    return await _view(session, principal, scholar)


async def _enrolment(
    session: AsyncSession, principal: Principal, enrolment_id: uuid.UUID
) -> tuple[Enrolment, Scholar]:
    e = await session.scalar(
        select(Enrolment).where(Enrolment.id == enrolment_id, Enrolment.deleted_at.is_(None))
    )
    if e is None:
        raise forbidden()
    scholar = await scope.get_scholar_or_403(session, principal, e.scholar_id, "enrolments")
    await coursework.require_unlocked(session, scholar.id)
    return e, scholar


@router.patch("/enrolments/{enrolment_id}", response_model=CourseworkView)
async def grade(
    enrolment_id: uuid.UUID,
    body: EnrolmentUpdate,
    principal: Principal = Depends(require_perm("enrolments", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    e, scholar = await _enrolment(session, principal, enrolment_id)
    await update(session, principal, e, body.model_dump(exclude_unset=True))
    await session.commit()
    return await _view(session, principal, scholar)


@router.delete("/enrolments/{enrolment_id}", response_model=CourseworkView)
async def unenrol(
    enrolment_id: uuid.UUID,
    principal: Principal = Depends(require_perm("enrolments", "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    e, scholar = await _enrolment(session, principal, enrolment_id)
    await soft_delete(session, principal, e)
    await session.commit()
    return await _view(session, principal, scholar)


@router.post("/clearances", response_model=ItemView, status_code=201)
async def start_clearance(
    body: ClearanceIn,
    principal: Principal = Depends(require_perm("coursework_clearances", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """A draft; the Exam Office submits it on /items, where the rules are checked."""
    scholar = await scope.get_scholar_or_403(
        session, principal, body.scholar_id, "coursework_clearances"
    )
    c = await insert(session, principal, CourseworkClearance(scholar_id=scholar.id))
    await session.commit()
    ctx = await items.load_ctx(session, principal, "coursework_clearance", c.id)
    return await items.view(session, principal, ctx)
