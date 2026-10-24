"""Research projects (PRD M7, UX Flow 11): funded projects with their PI, agency, sanction and
member scholars. Admins over the project's unit and the research office manage them; the PI
sees their own, a scholar the projects they belong to, heads their subtree."""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import grants, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import ProjectStatus
from app.errors import ApiError, forbidden
from app.models import Faculty, OrgUnit, Project, ProjectMember, Scholar, User
from app.modules import module_enabled, require_module
from app.rbac import require_perm
from app.schemas import Ref
from app.schemas.grants import MemberIn, MemberOut, ProjectIn, ProjectOut, ProjectUpdate

router = APIRouter(
    prefix="/projects", tags=["projects"], dependencies=[Depends(require_module("projects"))]
)


def _query(principal: Principal) -> Select:
    return (
        select(
            Project,
            User.full_name,
            OrgUnit.name,
            OrgUnit.path,
            scope.project_predicate(principal, ledger=True).label("sees_ledger"),
        )
        .join(Faculty, Faculty.id == Project.pi_id)
        .join(User, User.id == Faculty.user_id)
        .join(OrgUnit, OrgUnit.id == Project.unit_id)
        .where(Project.deleted_at.is_(None), scope.project_predicate(principal))
    )


async def _members(
    session: AsyncSession, project_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[MemberOut]]:
    out: dict[uuid.UUID, list[MemberOut]] = defaultdict(list)
    rows = await session.execute(
        select(ProjectMember, Scholar.roll_number, User.full_name)
        .join(Scholar, Scholar.id == ProjectMember.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .where(ProjectMember.project_id.in_(project_ids), ProjectMember.deleted_at.is_(None))
        .order_by(User.full_name)
    )
    for m, roll, name in rows:
        out[m.project_id].append(
            MemberOut(
                id=m.id,
                scholar=Ref(id=m.scholar_id, name=name),
                roll_number=roll,
                member_role=m.member_role,
            )
        )
    return out


async def _outs(session: AsyncSession, principal: Principal, rows) -> list[ProjectOut]:
    rows = list(rows)
    members = await _members(session, [r[0].id for r in rows])
    ledger_on = await module_enabled(session, "ledger")
    return [
        ProjectOut(
            id=p.id,
            title=p.title,
            agency=p.agency,
            sanction_number=p.sanction_number,
            amount_sanctioned=p.amount_sanctioned,
            start_date=p.start_date,
            end_date=p.end_date,
            status=p.status,
            pi=Ref(id=p.pi_id, name=pi_name),
            unit=Ref(id=p.unit_id, name=unit_name),
            members=members.get(p.id, []),
            can_manage=grants.may_manage(principal, path),
            sees_ledger=ledger_on and bool(sees_ledger),
        )
        for p, pi_name, unit_name, path, sees_ledger in rows
    ]


async def _one(session: AsyncSession, principal: Principal, project_id: uuid.UUID) -> ProjectOut:
    rows = (await session.execute(_query(principal).where(Project.id == project_id))).all()
    if not rows:
        raise forbidden()
    return (await _outs(session, principal, rows))[0]


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    unit_id: uuid.UUID | None = None,
    status: ProjectStatus | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    principal: Principal = Depends(current_principal),  # scope decides (PIs, members)
    session: AsyncSession = Depends(get_session),
) -> list[ProjectOut]:
    stmt = _query(principal)
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Project.unit_id.in_(scope.subtree_unit_ids((path,))))
    if status:
        stmt = stmt.where(Project.status == status)
    rows = await session.execute(stmt.order_by(Project.start_date.desc()).limit(limit))
    return await _outs(session, principal, rows)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_principal),  # scope decides (PIs, members)
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    return await _one(session, principal, project_id)


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectIn,
    principal: Principal = Depends(require_perm("projects", "create")),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    pi = await session.scalar(
        select(Faculty).where(Faculty.id == body.pi_id, Faculty.deleted_at.is_(None))
    )
    if pi is None:
        raise ApiError(422, "pi_not_found", "The principal investigator is not on record.")
    unit_id = body.unit_id or pi.unit_id
    grants.require_manage(principal, await scope.unit_path(session, unit_id))
    p = await insert(session, principal, Project(**body.model_dump() | {"unit_id": unit_id}))
    await session.commit()
    return await _one(session, principal, p.id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    principal: Principal = Depends(require_perm("projects", "update")),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    p, path = await grants.project_or_403(session, principal, project_id)
    grants.require_manage(principal, path)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    grants.check_dates(changes.get("start_date", p.start_date), changes.get("end_date", p.end_date))
    await update(session, principal, p, changes)
    await session.commit()
    return await _one(session, principal, project_id)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_perm("projects", "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    p, path = await grants.project_or_403(session, principal, project_id)
    grants.require_manage(principal, path)
    await soft_delete(session, principal, p)
    await session.commit()


@router.post("/{project_id}/members", response_model=ProjectOut, status_code=201)
async def add_member(
    project_id: uuid.UUID,
    body: MemberIn,
    principal: Principal = Depends(require_perm("projects", "update")),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    """Members may come from any unit — a project can fund scholars across departments."""
    _, path = await grants.project_or_403(session, principal, project_id)
    grants.require_manage(principal, path)
    live = await session.scalar(
        select(Scholar.id).where(Scholar.id == body.scholar_id, Scholar.deleted_at.is_(None))
    )
    if live is None:
        raise ApiError(422, "scholar_not_found", "This scholar is not on record.")
    await insert(session, principal, ProjectMember(project_id=project_id, **body.model_dump()))
    await session.commit()
    return await _one(session, principal, project_id)


@router.delete("/{project_id}/members/{member_id}", response_model=ProjectOut)
async def remove_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    principal: Principal = Depends(require_perm("projects", "update")),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    _, path = await grants.project_or_403(session, principal, project_id)
    grants.require_manage(principal, path)
    m = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.id == member_id,
            ProjectMember.project_id == project_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    if m is None:
        raise forbidden()
    await soft_delete(session, principal, m)
    await session.commit()
    return await _one(session, principal, project_id)
