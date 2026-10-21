"""Users, their profiles and role assignments — scoped admin management (PRD F2, Flow 5)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.auth.service import hash_password
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import UGC_CAP, UNIT_ROLES
from app.errors import ApiError, forbidden
from app.models import Faculty, OrgUnit, RoleAssignment, Scholar, User
from app.rbac import require_perm
from app.schemas import (
    RoleAssignmentIn,
    RoleAssignmentOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(tags=["people"])

MAX_PAGE = 200


async def _user_unit_paths(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Units a user belongs to via profile or role — what decides which admins manage them."""
    profile_units = (
        select(Scholar.unit_id)
        .where(Scholar.user_id == user_id, Scholar.deleted_at.is_(None))
        .union(
            select(Faculty.unit_id).where(Faculty.user_id == user_id, Faculty.deleted_at.is_(None)),
            select(RoleAssignment.unit_id).where(
                RoleAssignment.user_id == user_id,
                RoleAssignment.unit_id.is_not(None),
                RoleAssignment.deleted_at.is_(None),
            ),
        )
    )
    rows = await session.scalars(select(OrgUnit.path).where(OrgUnit.id.in_(profile_units)))
    return list(rows)


async def _require_admin_over_user(
    session: AsyncSession, principal: Principal, user_id: uuid.UUID
) -> None:
    if principal.is_root_admin:
        return
    paths = await _user_unit_paths(session, user_id)
    if not any(principal.covers("admin", p) for p in paths):
        raise forbidden()


@router.get("/users", response_model=list[UserOut])
async def list_users(
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    stmt = select(User).where(User.deleted_at.is_(None), scope.user_predicate(principal))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(User.full_name.ilike(like) | User.email.ilike(like))
    rows = await session.scalars(stmt.order_by(User.full_name).limit(limit).offset(offset))
    return list(rows)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> User:
    return await scope.get_user_or_403(session, principal, user_id)


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    principal: Principal = Depends(require_perm("users", "create")),
    session: AsyncSession = Depends(get_session),
) -> User:
    profile = body.faculty or body.scholar
    if profile is None:
        # Bare accounts (office staff) belong to no unit: only the root admin creates them.
        if not principal.is_root_admin:
            raise forbidden()
    else:
        scope.require_admin_over(principal, await scope.unit_path(session, profile.unit_id))

    user = await insert(
        session,
        principal,
        User(
            email=body.email,
            full_name=body.full_name,
            password_hash=hash_password(body.password),
        ),
    )
    if body.faculty:
        await insert(
            session,
            principal,
            Faculty(
                user_id=user.id,
                unit_id=body.faculty.unit_id,
                designation=body.faculty.designation,
                employee_id=body.faculty.employee_id,
                can_supervise=body.faculty.can_supervise,
                max_scholars=UGC_CAP[body.faculty.designation],
            ),
        )
    if body.scholar:
        await insert(
            session,
            principal,
            Scholar(
                user_id=user.id,
                unit_id=body.scholar.unit_id,
                roll_number=body.scholar.roll_number,
                research_title=body.scholar.research_title,
                admission_date=body.scholar.admission_date,
            ),
        )
    await session.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    principal: Principal = Depends(require_perm("users", "update")),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await scope.get_user_or_403(session, principal, user_id)
    await _require_admin_over_user(session, principal, user_id)
    if body.is_active is False and user_id == principal.user_id:
        raise ApiError(422, "cannot_deactivate_self", "You cannot deactivate your own account.")
    await update(session, principal, user, body.model_dump(exclude_unset=True))
    await session.commit()
    return user


@router.get("/users/{user_id}/roles", response_model=list[RoleAssignmentOut])
async def list_roles(
    user_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[RoleAssignment]:
    await scope.get_user_or_403(session, principal, user_id)
    rows = await session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user_id, RoleAssignment.deleted_at.is_(None)
        )
    )
    return list(rows)


async def _require_may_grant(
    session: AsyncSession, principal: Principal, role: str, unit_id: uuid.UUID | None
) -> None:
    """Unit roles: admin at or above that unit. Office roles: root admin only."""
    if role in UNIT_ROLES:
        if unit_id is None:
            raise ApiError(422, "unit_required", "This role needs a unit.")
        scope.require_admin_over(principal, await scope.unit_path(session, unit_id))
        return
    if unit_id is not None:
        raise ApiError(422, "unit_not_allowed", "Office roles are university-wide.")
    if not principal.is_root_admin:
        raise forbidden()


@router.post("/role-assignments", response_model=RoleAssignmentOut, status_code=201)
async def assign_role(
    body: RoleAssignmentIn,
    principal: Principal = Depends(require_perm("users", "manage_roles")),
    session: AsyncSession = Depends(get_session),
) -> RoleAssignment:
    await _require_may_grant(session, principal, body.role, body.unit_id)
    target = await session.get(User, body.user_id)
    if target is None or target.deleted_at is not None:
        raise ApiError(422, "user_not_found", "This user does not exist.")
    row = await insert(
        session,
        principal,
        RoleAssignment(
            user_id=body.user_id,
            role=body.role,
            unit_id=body.unit_id,
        ),
    )
    await session.commit()
    return row


@router.delete("/role-assignments/{assignment_id}", status_code=204)
async def revoke_role(
    assignment_id: uuid.UUID,
    principal: Principal = Depends(require_perm("users", "manage_roles")),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await session.get(RoleAssignment, assignment_id)
    if row is None or row.deleted_at is not None:
        raise forbidden()
    await _require_may_grant(session, principal, row.role, row.unit_id)
    if row.user_id == principal.user_id and row.role == "admin" and principal.is_root_admin:
        raise ApiError(
            422,
            "cannot_revoke_own_root_admin",
            "Ask another university administrator to remove your admin role.",
        )
    await soft_delete(session, principal, row)
    await session.commit()
