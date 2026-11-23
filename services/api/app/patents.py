"""Patents (PRD M10): a member of faculty or a scholar records their own; the office the
university chose (settings.patent_verifier: the Research Office or the Library) verifies each or
returns it with a note (verification.py). No approval chain. A patent moves on after it is
checked (filed -> published -> granted), so the author may update a verified one; the update
sends it back to the office. Only verified patents count in the NAAC sheet (naac.py)."""

import uuid
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import scope, verification
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.errors import ApiError, forbidden
from app.models import Faculty, OrgUnit, Patent, Scholar, Settings, User
from app.modules import module_enabled
from app.rbac import can

ENTITY = "patents"
Checker = aliased(User)
VERIFIER_LABELS = {"research_office": "the Research Office", "library": "the Library"}


async def verifier(session: AsyncSession) -> str:
    settings = await session.get(Settings, 1)
    assert settings is not None, "settings row is seeded by migration 0001"
    return settings.patent_verifier


def require_reader(principal: Principal) -> None:
    """Their own (faculty or scholar), or a role the matrix lets read patents."""
    if principal.faculty_id is None and not can(principal, ENTITY, "read"):
        raise forbidden()


def owner_of(principal: Principal) -> dict[str, uuid.UUID]:
    """Whose patent a new one is: a member of faculty's (also when they are a scholar too), else
    the scholar's."""
    if principal.faculty_id:
        return {"faculty_id": principal.faculty_id}
    if principal.scholar_id:
        return {"scholar_id": principal.scholar_id}
    raise ApiError(403, "forbidden", "Members of faculty and scholars record their own patents.")


def base_query(principal: Principal) -> Select[Any]:
    return (
        select(Patent, User.full_name, User.id, OrgUnit.name, Checker.full_name)
        .outerjoin(Faculty, Faculty.id == Patent.faculty_id)
        .outerjoin(Scholar, Scholar.id == Patent.scholar_id)
        .join(User, User.id == func.coalesce(Faculty.user_id, Scholar.user_id))
        .join(OrgUnit, OrgUnit.id == func.coalesce(Faculty.unit_id, Scholar.unit_id))
        .outerjoin(Checker, Checker.id == Patent.checked_by)
        .where(Patent.deleted_at.is_(None), scope.patent_predicate(principal))
    )


async def get_or_403(session: AsyncSession, principal: Principal, patent_id: uuid.UUID) -> Any:
    require_reader(principal)
    row = (await session.execute(base_query(principal).where(Patent.id == patent_id))).first()
    if row is None:
        raise forbidden()
    return row


def row_out(p: Patent, name: str, unit: str) -> dict[str, Any]:
    return {
        "id": p.id,
        "owner": {"id": p.faculty_id or p.scholar_id, "name": name},
        "owner_kind": "faculty" if p.faculty_id else "scholar",
        "unit": unit,
        "title": p.title,
        "application_number": p.application_number,
        "filed_on": p.filed_on,
        "patent_status": p.patent_status,
        "granted_on": p.granted_on,
        "verification": p.verification,
        "updated_at": p.updated_at,
    }


def is_author(principal: Principal, p: Patent) -> bool:
    if p.faculty_id:
        return principal.faculty_id == p.faculty_id
    return principal.scholar_id == p.scholar_id


def can_check(principal: Principal, p: Patent, office: str) -> bool:
    """The chosen office, never on its own patent."""
    return office in principal.office_roles and not is_author(principal, p)


async def view(session: AsyncSession, principal: Principal, row: Any) -> dict[str, Any]:
    p, name, _, unit, checker = row
    office = await verifier(session)
    return row_out(p, name, unit) | {
        "inventors": p.inventors,
        "office": p.office,
        "published_on": p.published_on,
        "patent_number": p.patent_number,
        "return_note": verification.note_of(p),
        "checked_at": p.checked_at,
        "checked_by": checker,
        "verifier": office,
        "can_edit": is_author(principal, p),
        "can_check": can_check(principal, p, office),
    }


async def _tell_office(session: AsyncSession, principal: Principal, title: str) -> None:
    link = "/patents?verification=waiting"
    await verification.tell_office(session, principal, await verifier(session), title, link)


async def create(session: AsyncSession, principal: Principal, data: dict[str, Any]) -> Patent:
    patent = await insert(session, principal, Patent(**owner_of(principal), **data))
    await _tell_office(session, principal, f"{principal.full_name} added a patent to verify")
    return patent


def require_author(principal: Principal, p: Patent) -> None:
    if not is_author(principal, p):
        raise forbidden()


def require_attachable(principal: Principal, p: Patent) -> None:
    """Its papers (filing receipt, grant certificate) go on while it is not verified: to add
    one later, the author updates the patent first, which sends it back to be checked."""
    require_author(principal, p)
    if p.verification == "verified":
        raise ApiError(
            409,
            "already_verified",
            "This patent is verified. Update its details first; it then goes back to be checked.",
        )


async def edit(
    session: AsyncSession, principal: Principal, p: Patent, data: dict[str, Any]
) -> None:
    """The author's update, whole (the form sends every field); verified or returned, it goes
    back to the office."""
    require_author(principal, p)
    if p.verification != "waiting":
        data |= verification.BACK_TO_WAITING
        await _tell_office(session, principal, f"{principal.full_name} updated a patent to verify")
    await update(session, principal, p, data)


async def remove(session: AsyncSession, principal: Principal, p: Patent) -> None:
    require_author(principal, p)
    if p.verification == "verified":
        raise ApiError(409, "already_verified", "A verified patent stays on record.")
    await soft_delete(session, principal, p)


def _link(p: Patent) -> str:
    return f"/patents/{p.id}"


async def verify(session: AsyncSession, principal: Principal, row: Any) -> None:
    p, _, author, _, _ = row
    if not can_check(principal, p, await verifier(session)):
        raise forbidden()
    await verification.verify(session, principal, p, {}, author, p.title, _link(p))


async def return_(session: AsyncSession, principal: Principal, row: Any, note: str) -> None:
    p, _, author, _, _ = row
    if not can_check(principal, p, await verifier(session)):
        raise forbidden()
    await verification.return_(session, principal, p, note, author, p.title, _link(p))


async def home(session: AsyncSession, principal: Principal) -> dict[str, Any] | None:
    """Home's tiles: patents waiting for the verifying office (not its own), and the author's
    patents it returned. None for someone neither, or with the module off."""
    office = await verifier(session)
    checks = office in principal.office_roles
    authors = principal.faculty_id or principal.scholar_id
    if not (checks or authors) or not await module_enabled(session, "patents"):
        return None
    ids = ((Patent.faculty_id, principal.faculty_id), (Patent.scholar_id, principal.scholar_id))
    mine = [column == me for column, me in ids if me]
    # Not the caller's own; a patent of the other kind has NULL there, hence IS DISTINCT FROM.
    others = [column.is_distinct_from(me) for column, me in ids if me]
    live = Patent.deleted_at.is_(None)

    async def count(*where: ColumnElement[bool]) -> int:
        return await session.scalar(select(func.count()).where(live, *where)) or 0

    return {
        "checks": checks,  # the caller is in the verifying office
        "to_verify": await count(Patent.verification == "waiting", *others) if checks else 0,
        "returned": await count(Patent.verification == "returned", or_(*mine)) if mine else 0,
    }
