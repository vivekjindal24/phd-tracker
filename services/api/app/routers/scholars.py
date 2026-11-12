"""Scholar directory (PRD F6, UX Flow 5). Lists and details are scoped by scope.py."""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import directory, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import update
from app.db import get_session
from app.enums import STAGES, Stage, StudyMode
from app.errors import ApiError, forbidden
from app.models import Faculty, OrgUnit, Scholar, User
from app.rbac import require_perm
from app.schemas import AssignIn, Ref, ScholarOut, ScholarOwnProfile, ScholarUpdate
from app.sorting import Sort, ordered, page_of, ranked

router = APIRouter(prefix="/scholars", tags=["directory"])

SupFaculty = aliased(Faculty)
SupUser = aliased(User)
CoFaculty = aliased(Faculty)
CoUser = aliased(User)


def _query(principal: Principal) -> Select:
    return (
        select(
            Scholar,
            User.full_name,
            User.email,
            OrgUnit.name,
            SupUser.full_name,
            CoUser.full_name,
            OrgUnit.path,
        )
        .join(User, User.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .outerjoin(SupFaculty, SupFaculty.id == Scholar.supervisor_id)
        .outerjoin(SupUser, SupUser.id == SupFaculty.user_id)
        .outerjoin(CoFaculty, CoFaculty.id == Scholar.co_supervisor_id)
        .outerjoin(CoUser, CoUser.id == CoFaculty.user_id)
        .where(Scholar.deleted_at.is_(None), scope.scholar_directory_predicate(principal))
    )


def _out(row, principal: Principal) -> ScholarOut:
    s, name, email, unit_name, sup_name, co_name, unit_path = row
    personal = scope.sees_personal(principal, s.id, unit_path)
    return ScholarOut(
        id=s.id,
        user_id=s.user_id,
        full_name=name,
        email=email,
        roll_number=s.roll_number,
        unit=Ref(id=s.unit_id, name=unit_name),
        stage=s.stage,
        research_title=s.research_title,
        admission_date=s.admission_date,
        supervisor=Ref(id=s.supervisor_id, name=sup_name) if s.supervisor_id else None,
        co_supervisor=(
            Ref(id=s.co_supervisor_id, name=co_name)
            if s.co_supervisor_id and principal.co_supervision != "off"
            else None
        ),
        left_on=s.left_on,
        left_reason=s.left_reason,
        study_mode=s.study_mode,
        sees_personal=personal,
        gender=s.gender if personal else None,
        category=s.category if personal else None,
        has_disability=s.has_disability if personal else None,
    )


async def _one(session: AsyncSession, principal: Principal, scholar_id: uuid.UUID) -> ScholarOut:
    row = (await session.execute(_query(principal).where(Scholar.id == scholar_id))).first()
    if row is None:
        raise forbidden()
    return _out(row, principal)


@router.get("", response_model=list[ScholarOut])
async def list_scholars(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    stage: Stage | None = None,
    supervisor_id: uuid.UUID | None = None,
    mine: bool = False,
    study_mode: StudyMode | None = None,
    sort: Sort = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ScholarOut]:
    stmt = _query(principal)
    stmt = await scope.narrow_to_scholars(session, stmt, q, unit_id, Scholar.research_title)
    if stage:
        stmt = stmt.where(Scholar.stage == stage)
    if supervisor_id:
        stmt = stmt.where(Scholar.supervisor_id == supervisor_id)
    if mine:
        stmt = stmt.where(scope.own_scholars(principal))
    if study_mode:
        stmt = stmt.where(Scholar.study_mode == study_mode)
    columns = {
        "name": User.full_name,
        "roll_number": Scholar.roll_number,
        "department": OrgUnit.name,
        "stage": ranked(Scholar.stage, STAGES),
        "supervisor": SupUser.full_name,
    }
    stmt = ordered(stmt, sort, columns, [User.full_name], Scholar.id)
    rows = await page_of(session, response, stmt, limit, offset)
    return [_out(r, principal) for r in rows]


@router.get("/{scholar_id}", response_model=ScholarOut)
async def get_scholar(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    out = await _one(session, principal, scholar_id)
    if principal.directory_wide:
        records = await session.scalar(
            select(Scholar.id).where(
                Scholar.id == scholar_id, scope.scholar_predicate(principal, "scholars")
            )
        )
        out.directory_only = records is None
    return out


@router.patch("/{scholar_id}", response_model=ScholarOut)
async def update_scholar(
    scholar_id: uuid.UUID,
    body: ScholarUpdate,
    principal: Principal = Depends(require_perm("scholars", "update")),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    await directory.require_admin_over_scholar(session, principal, scholar)
    changes = body.model_dump(exclude_unset=True)
    if "unit_id" in changes:  # moving a scholar needs admin over the destination too
        scope.require_admin_over(principal, await scope.unit_path(session, changes["unit_id"]))
    was_current = directory.counts_toward_cap(scholar)
    await update(session, principal, scholar, changes)
    if not was_current:  # back from "left" / "Degree Awarded": the cap applies again
        await directory.recheck_cap(session, scholar)
    await session.commit()
    return await _one(session, principal, scholar_id)


@router.put("/mine/profile", response_model=ScholarOut)
async def fill_own_profile(
    body: ScholarOwnProfile,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    """A scholar fills in their own profile fields that are still not recorded (PRD F6). Once
    a field holds a value only the admin over their unit changes it."""
    if principal.scholar_id is None:
        raise forbidden()
    scholar = await session.get(Scholar, principal.scholar_id, with_for_update=True)
    assert scholar is not None
    changes = body.model_dump(exclude_none=True)
    recorded = sorted(k for k in changes if getattr(scholar, k) is not None)
    if recorded:
        raise ApiError(
            409,
            "already_recorded",
            "This is already on your record. Ask your department's admin to correct it.",
            {"fields": recorded},
        )
    await update(session, principal, scholar, changes)
    await session.commit()
    return await _one(session, principal, scholar.id)


@router.put("/{scholar_id}/supervisor", response_model=ScholarOut)
async def set_supervisor(
    scholar_id: uuid.UUID,
    body: AssignIn,
    principal: Principal = Depends(require_perm("scholars", "assign_supervisor")),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    await directory.assign_supervisor(session, principal, scholar, body.faculty_id)
    await session.commit()
    return await _one(session, principal, scholar_id)


@router.put("/{scholar_id}/co-supervisor", response_model=ScholarOut)
async def set_co_supervisor(
    scholar_id: uuid.UUID,
    body: AssignIn,
    principal: Principal = Depends(require_perm("scholars", "assign_supervisor")),
    session: AsyncSession = Depends(get_session),
) -> ScholarOut:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id)
    await directory.assign_co_supervisor(session, principal, scholar, body.faculty_id)
    await session.commit()
    return await _one(session, principal, scholar_id)
