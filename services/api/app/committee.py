"""Committees recorded in versions (PRD F9b): a scholar's Research Advisory Committee, whose
secretary is always the supervisor, and a department's research committee, whose members each
sit in a seat. Each formation is one version; the latest is the current committee."""

import uuid
from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.enums import COMMITTEE_ROLES
from app.models import CommitteeFormation, CommitteeMember, Faculty, OrgUnit, Scholar, User

ROLE_LABELS = {
    "chairperson": "Chairperson",
    "secretary": "Member and Secretary",
    "member": "Member",
    "vc_nominee": "Member (nominee of the Vice Chancellor)",
}
NEWEST_FIRST = (CommitteeFormation.formed_on.desc(), CommitteeFormation.created_at.desc())


def owned_by(formation: CommitteeFormation) -> ColumnElement[bool]:
    """Every version of the same committee as `formation`."""
    if formation.scholar_id is not None:
        return CommitteeFormation.scholar_id == formation.scholar_id
    return CommitteeFormation.unit_id == formation.unit_id


async def _faculty_name(session: AsyncSession, faculty_id: uuid.UUID | None) -> str | None:
    if faculty_id is None:
        return None
    return await session.scalar(
        select(User.full_name)
        .join(Faculty, Faculty.user_id == User.id)
        .where(Faculty.id == faculty_id)
    )


async def convener(session: AsyncSession, scholar: Scholar) -> str | None:
    return await _faculty_name(session, scholar.supervisor_id)


async def versions(session: AsyncSession, owner: ColumnElement[bool]) -> list[CommitteeFormation]:
    """Every live version of one committee, newest (the current one) first."""
    return list(
        await session.scalars(
            select(CommitteeFormation)
            .where(owner, CommitteeFormation.deleted_at.is_(None))
            .order_by(*NEWEST_FIRST)
        )
    )


async def current(session: AsyncSession, owner: ColumnElement[bool]) -> CommitteeFormation | None:
    found = await versions(session, owner)
    return found[0] if found else None


async def members(session: AsyncSession, formation_id: uuid.UUID) -> list[dict[str, Any]]:
    """Each member of one version in print order (chairperson first); the names and units of
    faculty and scholar members are read live."""
    member_user, member_unit = aliased(User), aliased(OrgUnit)
    rows = await session.execute(
        select(
            CommitteeMember,
            User.full_name,
            OrgUnit.name,
            member_user.full_name,
            member_unit.name,
        )
        .outerjoin(Faculty, Faculty.id == CommitteeMember.faculty_id)
        .outerjoin(User, User.id == Faculty.user_id)
        .outerjoin(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .outerjoin(Scholar, Scholar.id == CommitteeMember.scholar_member_id)
        .outerjoin(member_user, member_user.id == Scholar.user_id)
        .outerjoin(member_unit, member_unit.id == Scholar.unit_id)
        .where(CommitteeMember.formation_id == formation_id, CommitteeMember.deleted_at.is_(None))
    )
    out = [
        {
            "id": m.id,
            "name": m.name or faculty_name or scholar_name,
            "institution": m.institution or faculty_unit or scholar_unit,
            "external": m.name is not None,
            "role": m.role,
            "seat": m.seat,
        }
        for m, faculty_name, faculty_unit, scholar_name, scholar_unit in rows
    ]
    return sorted(out, key=lambda m: (COMMITTEE_ROLES.index(m["role"]), m["name"]))


async def formations(session: AsyncSession, owner: ColumnElement[bool]) -> list[dict[str, Any]]:
    """Every version with its members, newest (the current committee) first."""
    return [
        {
            "id": f.id,
            "formed_on": f.formed_on,
            "reference": f.reference,
            "notes": f.notes,
            "secretary": await _faculty_name(session, f.secretary_id),
            "members": await members(session, f.id),
        }
        for f in await versions(session, owner)
    ]


async def printed(session: AsyncSession, scholar: Scholar) -> list[str]:
    """The current advisory committee as the progress report prints it."""
    formation = await current(session, CommitteeFormation.scholar_id == scholar.id)
    if formation is None:
        return []
    return [
        f"{m['name']} ({m['institution']}), {ROLE_LABELS[m['role']]}"
        for m in await members(session, formation.id)
    ]
