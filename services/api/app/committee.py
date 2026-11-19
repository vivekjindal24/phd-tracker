"""A scholar's Research Advisory Committee (PRD F9b). Each formation is one version of it; the
latest is the current committee. The supervisor is its secretary; the other members are
recorded per formation with a role, faculty of this university or outside experts."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import COMMITTEE_ROLES
from app.models import CommitteeFormation, CommitteeMember, Faculty, OrgUnit, Scholar, User

ROLE_LABELS = {
    "chairperson": "Chairperson",
    "member": "Member",
    "vc_nominee": "Member (nominee of the Vice Chancellor)",
}


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


async def current(session: AsyncSession, scholar_id: uuid.UUID) -> CommitteeFormation | None:
    return await session.scalar(
        select(CommitteeFormation)
        .where(CommitteeFormation.scholar_id == scholar_id, CommitteeFormation.deleted_at.is_(None))
        .order_by(CommitteeFormation.formed_on.desc(), CommitteeFormation.created_at.desc())
        .limit(1)
    )


async def members(session: AsyncSession, formation_id: uuid.UUID) -> list[dict[str, Any]]:
    """Each member of one formation, chairperson first; an internal member's name and
    unit are read live."""
    rows = await session.execute(
        select(CommitteeMember, User.full_name, OrgUnit.name)
        .outerjoin(Faculty, Faculty.id == CommitteeMember.faculty_id)
        .outerjoin(User, User.id == Faculty.user_id)
        .outerjoin(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .where(CommitteeMember.formation_id == formation_id, CommitteeMember.deleted_at.is_(None))
    )
    out = [
        {
            "id": m.id,
            "name": m.name or full_name,
            "institution": m.institution or unit,
            "external": m.faculty_id is None,
            "role": m.role,
        }
        for m, full_name, unit in rows
    ]
    return sorted(out, key=lambda m: (COMMITTEE_ROLES.index(m["role"]), m["name"]))


async def formations(session: AsyncSession, scholar_id: uuid.UUID) -> list[dict[str, Any]]:
    """Every version, newest (the current committee) first."""
    rows = await session.scalars(
        select(CommitteeFormation)
        .where(CommitteeFormation.scholar_id == scholar_id, CommitteeFormation.deleted_at.is_(None))
        .order_by(CommitteeFormation.formed_on.desc(), CommitteeFormation.created_at.desc())
    )
    return [
        {
            "id": f.id,
            "formed_on": f.formed_on,
            "reference": f.reference,
            "notes": f.notes,
            "secretary": await _faculty_name(session, f.secretary_id),
            "members": await members(session, f.id),
        }
        for f in rows
    ]


async def printed(session: AsyncSession, scholar: Scholar) -> list[str]:
    """The current committee as the progress report prints it."""
    formation = await current(session, scholar.id)
    if formation is None:
        return []
    return [
        f"{m['name']} ({m['institution']}), {ROLE_LABELS[m['role']]}"
        for m in await members(session, formation.id)
    ]
