"""Progress seminar rules (PRD F15): who sees a seminar, who manages it, who is told."""

import uuid

from sqlalchemy import ColumnElement, cast, literal, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.errors import ApiError, forbidden
from app.models import (
    Faculty,
    OrgUnit,
    RoleAssignment,
    Scholar,
    Seminar,
    SeminarPanel,
    SeminarScholar,
    Settings,
)
from app.models.base import Ltree


def _live_scholar_seminars(*conditions: ColumnElement[bool]):
    return (
        select(SeminarScholar.seminar_id)
        .join(Scholar, Scholar.id == SeminarScholar.scholar_id)
        .where(SeminarScholar.deleted_at.is_(None), *conditions)
    )


def visible(principal: Principal) -> ColumnElement[bool]:
    if "research_office" in principal.office_roles or principal.is_root_admin:
        return true()
    clauses: list[ColumnElement[bool]] = []
    paths = tuple(r.unit_path for r in principal.unit_roles)
    if paths:  # heads and admins: their unit's seminars and every unit below
        clauses.append(Seminar.unit_id.in_(scope.subtree_unit_ids(paths)))
    if principal.scholar_id:
        clauses.append(Seminar.id.in_(_live_scholar_seminars(Scholar.id == principal.scholar_id)))
    fid = principal.faculty_id
    if fid:
        clauses.append(
            Seminar.id.in_(
                select(SeminarPanel.seminar_id).where(
                    SeminarPanel.faculty_id == fid, SeminarPanel.deleted_at.is_(None)
                )
            )
        )
        supervised = [Scholar.supervisor_id == fid]
        if principal.co_supervision != "off":
            supervised.append(Scholar.co_supervisor_id == fid)
        clauses.append(Seminar.id.in_(_live_scholar_seminars(or_(*supervised))))
    return or_(*clauses) if clauses else literal(False)


def can_manage(principal: Principal, unit_path: str) -> bool:
    return principal.covers("unit_head", unit_path) or principal.covers("admin", unit_path)


async def get_seminar(
    session: AsyncSession, principal: Principal, seminar_id: uuid.UUID
) -> tuple[Seminar, str]:
    row = (
        await session.execute(
            select(Seminar, OrgUnit.path)
            .join(OrgUnit, OrgUnit.id == Seminar.unit_id)
            .where(Seminar.id == seminar_id, Seminar.deleted_at.is_(None), visible(principal))
        )
    ).first()
    if row is None:
        raise forbidden()
    return row[0], row[1]


def require_manager(principal: Principal, unit_path: str) -> None:
    if not can_manage(principal, unit_path):
        raise forbidden()


async def check_scholars_in_unit(
    session: AsyncSession, unit_path: str, scholar_ids: list[uuid.UUID]
) -> None:
    found = set(
        await session.scalars(
            select(Scholar.id).where(
                Scholar.id.in_(scholar_ids),
                Scholar.deleted_at.is_(None),
                Scholar.unit_id.in_(scope.subtree_unit_ids((unit_path,))),
            )
        )
    )
    missing = [str(s) for s in scholar_ids if s not in found]
    if missing:
        raise ApiError(
            422,
            "scholar_outside_unit",
            "Some selected scholars are not in this unit.",
            {"scholar_ids": missing},
        )


async def check_faculty(session: AsyncSession, faculty_ids: list[uuid.UUID]) -> None:
    found = set(
        await session.scalars(
            select(Faculty.id).where(Faculty.id.in_(faculty_ids), Faculty.deleted_at.is_(None))
        )
    )
    missing = [str(f) for f in faculty_ids if f not in found]
    if missing:
        raise ApiError(
            422, "faculty_not_found", "Some panel members do not exist.", {"faculty_ids": missing}
        )


async def recipients(session: AsyncSession, seminar: Seminar, unit_path: str) -> list[uuid.UUID]:
    """Scholars, their supervisors (+co-supervisors when on), heads of the unit and every
    unit above, and the panel (PRD F15)."""
    co_on = (await session.scalar(select(Settings.co_supervision))) != "off"
    scholars = (
        await session.execute(
            select(Scholar.user_id, Scholar.supervisor_id, Scholar.co_supervisor_id)
            .join(SeminarScholar, SeminarScholar.scholar_id == Scholar.id)
            .where(SeminarScholar.seminar_id == seminar.id, SeminarScholar.deleted_at.is_(None))
        )
    ).all()
    faculty_ids = {s.supervisor_id for s in scholars if s.supervisor_id}
    if co_on:
        faculty_ids |= {s.co_supervisor_id for s in scholars if s.co_supervisor_id}
    faculty_ids |= set(
        await session.scalars(
            select(SeminarPanel.faculty_id).where(
                SeminarPanel.seminar_id == seminar.id, SeminarPanel.deleted_at.is_(None)
            )
        )
    )
    faculty_users = await session.scalars(
        select(Faculty.user_id).where(Faculty.id.in_(faculty_ids))
    )
    heads = await session.scalars(
        select(RoleAssignment.user_id)
        .join(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
        .where(
            RoleAssignment.role == "unit_head",
            RoleAssignment.deleted_at.is_(None),
            OrgUnit.path.op("@>")(cast(literal(unit_path), Ltree)),
        )
    )
    return list(dict.fromkeys([*(s.user_id for s in scholars), *faculty_users, *heads]))
