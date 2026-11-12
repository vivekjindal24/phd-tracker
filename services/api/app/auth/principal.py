"""The caller: identity plus every role they hold, loaded from the DB per request
(SECURITY.md §1 — roles are never trusted from the token)."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import READ_ALL_ROLES
from app.models import (
    Faculty,
    OrgUnit,
    RoleAssignment,
    Scholar,
    Settings,
    SupervisorStandIn,
    User,
)


@dataclass(frozen=True)
class UnitRole:
    role: str  # unit_head | admin
    unit_id: uuid.UUID
    unit_path: str
    cross_unit: bool = False  # the root admin opened this unit's directory


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str
    full_name: str
    co_supervision: str
    unit_roles: tuple[UnitRole, ...] = ()
    office_roles: frozenset[str] = field(default_factory=frozenset)
    faculty_id: uuid.UUID | None = None
    can_supervise: bool = False
    scholar_id: uuid.UUID | None = None
    root_path: str | None = None
    is_reviewer: bool = False
    # Supervisors (faculty ids) who named the caller as their stand-in for today.
    stands_in_for: tuple[uuid.UUID, ...] = ()

    @property
    def supervises(self) -> tuple[uuid.UUID, ...]:
        """Faculty ids whose scholars the caller reads and acts for as supervisor: their own,
        and those they stand in for today."""
        own = (self.faculty_id,) if self.faculty_id else ()
        return (*own, *self.stands_in_for)

    @property
    def roles(self) -> frozenset[str]:
        """Matrix roles held (SECURITY.md §2). Co-supervision rides on 'supervisor'."""
        held = set(self.office_roles) | {r.role for r in self.unit_roles}
        if self.scholar_id is not None:
            held.add("scholar")
        if self.faculty_id is not None and (
            self.can_supervise or self.co_supervision != "off" or self.stands_in_for
        ):
            held.add("supervisor")
        return frozenset(held)

    def unit_paths(self, role: str) -> tuple[str, ...]:
        return tuple(r.unit_path for r in self.unit_roles if r.role == role)

    @property
    def is_root_admin(self) -> bool:
        return self.root_path is not None and self.root_path in self.unit_paths("admin")

    @property
    def reads_all(self) -> bool:
        """Research Office or Vice Chancellor: every record the matrix lets them read."""
        return bool(self.office_roles & READ_ALL_ROLES)

    @property
    def directory_wide(self) -> bool:
        """A unit role in a department the root admin opened: the whole directory, read-only."""
        return any(r.cross_unit for r in self.unit_roles)

    def covers(self, role: str, unit_path: str) -> bool:
        """True if one of the caller's `role` assignments is unit_path or an ancestor of it."""
        return any(unit_path == p or unit_path.startswith(p + ".") for p in self.unit_paths(role))


async def load_principal(session: AsyncSession, user: User) -> Principal:
    assignments = (
        await session.execute(
            select(
                RoleAssignment.role,
                RoleAssignment.unit_id,
                OrgUnit.path,
                OrgUnit.cross_unit_directory,
            )
            .outerjoin(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
            .where(RoleAssignment.user_id == user.id, RoleAssignment.deleted_at.is_(None))
        )
    ).all()
    faculty = await session.scalar(
        select(Faculty).where(Faculty.user_id == user.id, Faculty.deleted_at.is_(None))
    )
    scholar_id = await session.scalar(
        select(Scholar.id).where(Scholar.user_id == user.id, Scholar.deleted_at.is_(None))
    )
    co_supervision = await session.scalar(select(Settings.co_supervision).where(Settings.id == 1))
    root_path = await session.scalar(
        select(OrgUnit.path).where(OrgUnit.parent_id.is_(None), OrgUnit.deleted_at.is_(None))
    )
    today = datetime.now(UTC).date()
    stands_in_for: tuple[uuid.UUID, ...] = ()
    if faculty:
        stands_in_for = tuple(
            await session.scalars(
                select(SupervisorStandIn.faculty_id).where(
                    SupervisorStandIn.stand_in_id == faculty.id,
                    SupervisorStandIn.deleted_at.is_(None),
                    SupervisorStandIn.starts_on <= today,
                    SupervisorStandIn.ends_on >= today,
                )
            )
        )
    return Principal(
        stands_in_for=stands_in_for,
        user_id=user.id,
        is_reviewer=user.is_reviewer,
        email=user.email,
        full_name=user.full_name,
        co_supervision=co_supervision or "off",
        unit_roles=tuple(
            UnitRole(role, unit_id, path, bool(cross_unit))
            for role, unit_id, path, cross_unit in assignments
            if unit_id
        ),
        office_roles=frozenset(role for role, unit_id, *_ in assignments if unit_id is None),
        faculty_id=faculty.id if faculty else None,
        can_supervise=bool(faculty and faculty.can_supervise),
        scholar_id=scholar_id,
        root_path=root_path,
    )
