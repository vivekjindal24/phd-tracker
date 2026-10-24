"""The single place visibility is computed (SECURITY.md §2). Every list, detail, search,
dashboard and export filters through these predicates. Out of scope -> 403, never 404."""

import uuid
from typing import TypeVar

from sqlalchemy import ColumnElement, cast, false, literal, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.enums import OFFICE_ROLES, UNIT_ROLES
from app.errors import forbidden
from app.models import OrgUnit, Project, ProjectMember, RoleAssignment, Scholar, User
from app.models.base import Ltree
from app.models.org import Faculty
from app.rbac import roles_allowed

T = TypeVar("T")


def subtree_unit_ids(paths: tuple[str, ...]):
    """Ids of every live unit at or below any of `paths`."""
    return select(OrgUnit.id).where(
        OrgUnit.deleted_at.is_(None),
        or_(*[OrgUnit.path.op("<@")(cast(literal(p), Ltree)) for p in paths]),
    )


def _unit_paths(principal: Principal, roles: frozenset[str]) -> tuple[str, ...]:
    return tuple(r.unit_path for r in principal.unit_roles if r.role in roles)


def scholar_predicate(principal: Principal, entity: str) -> ColumnElement[bool]:
    """Which scholars' records of `entity` the caller may read: the union over every role
    they hold that the matrix lets read the entity."""
    roles = principal.roles & roles_allowed(entity, "read")
    if roles & set(OFFICE_ROLES):
        return true()
    clauses: list[ColumnElement[bool]] = []
    if "scholar" in roles and principal.scholar_id:
        clauses.append(Scholar.id == principal.scholar_id)
    if "supervisor" in roles and principal.faculty_id:
        clauses.append(Scholar.supervisor_id == principal.faculty_id)
        if principal.co_supervision != "off":
            clauses.append(Scholar.co_supervisor_id == principal.faculty_id)
    paths = _unit_paths(principal, roles)
    if paths:
        clauses.append(Scholar.unit_id.in_(subtree_unit_ids(paths)))
    return or_(*clauses) if clauses else false()


def unit_predicate(principal: Principal, entity: str, unit_column) -> ColumnElement[bool]:
    """Records anchored on a unit rather than a scholar (admissions): offices see all, unit
    heads/admins their subtree (DATABASE.md §5)."""
    roles = principal.roles & roles_allowed(entity, "read")
    if roles & set(OFFICE_ROLES):
        return true()
    paths = _unit_paths(principal, roles)
    return unit_column.in_(subtree_unit_ids(paths)) if paths else false()


def project_predicate(principal: Principal, *, ledger: bool = False) -> ColumnElement[bool]:
    """Projects the caller may read (SECURITY.md §3): the research office all, unit heads and
    admins their subtree, the PI their own, a scholar the projects they belong to — but not
    the money (`ledger=True` drops members)."""
    if "research_office" in principal.office_roles:
        return true()
    clauses: list[ColumnElement[bool]] = []
    if principal.faculty_id:
        clauses.append(Project.pi_id == principal.faculty_id)
    if principal.scholar_id and not ledger:
        clauses.append(
            Project.id.in_(
                select(ProjectMember.project_id).where(
                    ProjectMember.scholar_id == principal.scholar_id,
                    ProjectMember.deleted_at.is_(None),
                )
            )
        )
    paths = _unit_paths(principal, frozenset(UNIT_ROLES))
    if paths:
        clauses.append(Project.unit_id.in_(subtree_unit_ids(paths)))
    return or_(*clauses) if clauses else false()


def fellowship_ledger_predicate(principal: Principal) -> ColumnElement[bool]:
    """Whose fellowship money the caller may read: the research office all, unit heads and
    admins their subtree. Scholars and supervisors see the fellowship, not its ledger."""
    if "research_office" in principal.office_roles:
        return true()
    paths = _unit_paths(principal, frozenset(UNIT_ROLES))
    return Scholar.unit_id.in_(subtree_unit_ids(paths)) if paths else false()


def user_predicate(principal: Principal) -> ColumnElement[bool]:
    """Users the caller may read: self, everyone for root admin / research office, and for
    scoped heads/admins the users whose profile or role assignment sits in their subtree."""
    if principal.is_root_admin or "research_office" in principal.roles:
        return true()
    clauses: list[ColumnElement[bool]] = [User.id == principal.user_id]
    paths = _unit_paths(principal, frozenset({"unit_head", "admin"}))
    if paths:
        units = subtree_unit_ids(paths)
        clauses += [
            User.id.in_(select(Scholar.user_id).where(Scholar.unit_id.in_(units))),
            User.id.in_(select(Faculty.user_id).where(Faculty.unit_id.in_(units))),
            User.id.in_(
                select(RoleAssignment.user_id).where(
                    RoleAssignment.unit_id.in_(units), RoleAssignment.deleted_at.is_(None)
                )
            ),
        ]
    return or_(*clauses)


async def unit_path(session: AsyncSession, unit_id: uuid.UUID) -> str:
    path = await session.scalar(
        select(OrgUnit.path).where(OrgUnit.id == unit_id, OrgUnit.deleted_at.is_(None))
    )
    if path is None:
        raise forbidden()
    return path


async def get_scholar_or_403(
    session: AsyncSession, principal: Principal, scholar_id: uuid.UUID, entity: str = "scholars"
) -> Scholar:
    scholar = await session.scalar(
        select(Scholar).where(
            Scholar.id == scholar_id,
            Scholar.deleted_at.is_(None),
            scholar_predicate(principal, entity),
        )
    )
    if scholar is None:
        raise forbidden()
    return scholar


async def get_user_or_403(session: AsyncSession, principal: Principal, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None), user_predicate(principal))
    )
    if user is None:
        raise forbidden()
    return user


def require_admin_over(principal: Principal, path: str) -> None:
    """Writes to a unit (or its people) need an admin assignment at or above that unit."""
    if not principal.covers("admin", path):
        raise forbidden()
