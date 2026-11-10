"""A scholar's Research Advisory Committee (PRD F9b): the supervisor convenes it; the other
members are recorded here, faculty of this university or outside experts."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CommitteeMember, Faculty, OrgUnit, Scholar, User


async def convener(session: AsyncSession, scholar: Scholar) -> str | None:
    return await session.scalar(
        select(User.full_name)
        .join(Faculty, Faculty.user_id == User.id)
        .where(Faculty.id == scholar.supervisor_id)
    )


async def members(session: AsyncSession, scholar: Scholar) -> list[dict[str, Any]]:
    """Name and institution of each member, by name; an internal member's are read live."""
    rows = await session.execute(
        select(CommitteeMember, User.full_name, OrgUnit.name)
        .outerjoin(Faculty, Faculty.id == CommitteeMember.faculty_id)
        .outerjoin(User, User.id == Faculty.user_id)
        .outerjoin(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .where(CommitteeMember.scholar_id == scholar.id, CommitteeMember.deleted_at.is_(None))
    )
    out = [
        {
            "id": m.id,
            "name": m.name or full_name,
            "institution": m.institution or unit,
            "external": m.faculty_id is None,
        }
        for m, full_name, unit in rows
    ]
    return sorted(out, key=lambda m: m["name"])
