"""The caller: identity plus every role they hold, loaded from the DB per request
(SECURITY.md §1 — roles are never trusted from the token)."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Faculty, OrgUnit, RoleAssignment, Scholar, Settings, User


@dataclass(frozen=True)
class UnitRole:
    role: str  # unit_head | admin
    unit_id: uuid.UUID
    unit_path: str


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

    @property
    def roles(self) -> frozenset[str]:
        """Matrix roles held (SECURITY.md §2). Co-supervision rides on 'supervisor'."""
        held = set(self.office_roles) | {r.role for r in self.unit_roles}
        if self.scholar_id is not None:
            held.add("scholar")
        if self.faculty_id is not None and (self.can_supervise or self.co_supervision != "off"):
            held.add("supervisor")
        return frozenset(held)

    def unit_paths(self, role: str) -> tuple[str, ...]:
        return tuple(r.unit_path for r in self.unit_roles if r.role == role)

    @property
    def is_root_admin(self) -> bool:
        return self.root_path is not None and self.root_path in self.unit_paths("admin")

    def covers(self, role: str, unit_path: str) -> bool:
        """True if one of the caller's `role` assignments is unit_path or an ancestor of it."""
        return any(unit_path == p or unit_path.startswith(p + ".") for p in self.unit_paths(role))


async def load_principal(session: AsyncSession, user: User) -> Principal:
    assignments = (
        await session.execute(
            select(RoleAssignment.role, RoleAssignment.unit_id, OrgUnit.path)
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
    return Principal(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        co_supervision=co_supervision or "off",
        unit_roles=tuple(
            UnitRole(role, unit_id, path) for role, unit_id, path in assignments if unit_id
        ),
        office_roles=frozenset(role for role, unit_id, _ in assignments if unit_id is None),
        faculty_id=faculty.id if faculty else None,
        can_supervise=bool(faculty and faculty.can_supervise),
        scholar_id=scholar_id,
        root_path=root_path,
    )
