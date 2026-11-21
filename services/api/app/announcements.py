"""The notice board (owner, 2026-11-22): notices for the whole university or for one department,
such as the fee notice the university's own system issues. Anveshan keeps no fees itself.

Who posts: the Research Office and the root admin, anywhere; an admin, for their unit and
everything below it. Who reads: everyone, a university-wide notice; a department's notice, the
people of that department (its scholars, faculty, heads and admins, and those of the units
inside it) and the heads and admins above it; the offices and the root admin, every notice."""

import uuid
from datetime import date

from sqlalchemy import ColumnElement, cast, exists, literal, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.errors import forbidden
from app.models import (
    Announcement,
    Faculty,
    OrgUnit,
    RoleAssignment,
    Scholar,
    User,
)
from app.models.base import Ltree
from app.scope import subtree_unit_ids


def may_post(principal: Principal, unit_path: str | None) -> bool:
    """`unit_path` None: the whole university."""
    if principal.is_root_admin or "research_office" in principal.office_roles:
        return True
    return unit_path is not None and principal.covers("admin", unit_path)


def require_post(principal: Principal, unit_path: str | None) -> None:
    if not may_post(principal, unit_path):
        raise forbidden()


def visible(principal: Principal) -> ColumnElement[bool]:
    """Which notices the caller reads (module docstring)."""
    if principal.is_root_admin or principal.office_roles:
        return true()
    home = OrgUnit.__table__.alias("home")
    mine: list[ColumnElement[bool]] = []  # the units the caller belongs to
    if principal.unit_roles:
        mine.append(home.c.id.in_([r.unit_id for r in principal.unit_roles]))
    if principal.scholar_id:
        mine.append(
            home.c.id.in_(select(Scholar.unit_id).where(Scholar.id == principal.scholar_id))
        )
    if principal.faculty_id:
        mine.append(
            home.c.id.in_(select(Faculty.unit_id).where(Faculty.id == principal.faculty_id))
        )
    clauses: list[ColumnElement[bool]] = [Announcement.unit_id.is_(None)]
    if mine:  # the notice's unit holds one of the caller's units
        notice_path = select(OrgUnit.path).where(OrgUnit.id == Announcement.unit_id)
        clauses.append(
            exists(select(1).where(or_(*mine), home.c.path.op("<@")(notice_path.scalar_subquery())))
        )
    paths = tuple(r.unit_path for r in principal.unit_roles)
    if paths:  # heads and admins: every notice of the units below them too
        clauses.append(Announcement.unit_id.in_(subtree_unit_ids(paths)))
    return or_(*clauses)


def current(today: date) -> ColumnElement[bool]:
    return or_(Announcement.ends_on.is_(None), Announcement.ends_on >= today)


async def get_or_403(
    session: AsyncSession, principal: Principal, notice_id: uuid.UUID
) -> Announcement:
    row = await session.scalar(
        select(Announcement).where(
            Announcement.id == notice_id, Announcement.deleted_at.is_(None), visible(principal)
        )
    )
    if row is None:
        raise forbidden()
    return row


async def path_of(session: AsyncSession, notice: Announcement) -> str | None:
    if notice.unit_id is None:
        return None
    return await session.scalar(select(OrgUnit.path).where(OrgUnit.id == notice.unit_id))


async def recipients(session: AsyncSession, unit_path: str | None) -> list[uuid.UUID]:
    """Who is told of a new notice: everyone, or the people of the unit and those above it."""
    active = (User.is_active.is_(True), User.deleted_at.is_(None))
    if unit_path is None:
        return list(await session.scalars(select(User.id).where(*active)))
    inside = subtree_unit_ids((unit_path,))
    above = select(OrgUnit.id).where(
        OrgUnit.deleted_at.is_(None), cast(literal(unit_path), Ltree).op("<@")(OrgUnit.path)
    )
    people = (
        select(Scholar.user_id)
        .where(Scholar.unit_id.in_(inside), Scholar.deleted_at.is_(None))
        .union(
            select(Faculty.user_id).where(
                Faculty.unit_id.in_(inside), Faculty.deleted_at.is_(None)
            ),
            select(RoleAssignment.user_id).where(
                or_(RoleAssignment.unit_id.in_(inside), RoleAssignment.unit_id.in_(above)),
                RoleAssignment.deleted_at.is_(None),
            ),
        )
        .subquery()
    )
    return list(await session.scalars(select(User.id).where(User.id.in_(select(people)), *active)))
