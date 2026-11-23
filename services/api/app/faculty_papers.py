"""Faculty publications (PRD M1): a member of faculty records their own papers, by hand, from a
DOI or from ORCID; the Library verifies each (correcting indexing and DOI) or returns it with a
note. No approval chain. Only verified papers count in the NAAC sheets (naac.py)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import notices, scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.errors import ApiError, forbidden
from app.models import Faculty, FacultyPublication, OrgUnit, User
from app.modules import module_enabled
from app.notify import notify
from app.rbac import can

ENTITY = "faculty_publications"
Checker = aliased(User)


def require_reader(principal: Principal) -> None:
    """Any member of faculty (their own papers), or a role the matrix lets read them."""
    if principal.faculty_id is None and not can(principal, ENTITY, "read"):
        raise forbidden()


def own_faculty(principal: Principal) -> uuid.UUID:
    if principal.faculty_id is None:
        raise ApiError(403, "forbidden", "Members of faculty record their own publications.")
    return principal.faculty_id


def base_query(principal: Principal) -> Select[Any]:
    return (
        select(FacultyPublication, Faculty, User.full_name, OrgUnit.name, Checker.full_name)
        .join(Faculty, Faculty.id == FacultyPublication.faculty_id)
        .join(User, User.id == Faculty.user_id)
        .join(OrgUnit, OrgUnit.id == Faculty.unit_id)
        .outerjoin(Checker, Checker.id == FacultyPublication.checked_by)
        .where(
            FacultyPublication.deleted_at.is_(None),
            scope.faculty_publication_predicate(principal),
        )
    )


async def get_or_403(session: AsyncSession, principal: Principal, pub_id: uuid.UUID) -> Any:
    require_reader(principal)
    row = (
        await session.execute(base_query(principal).where(FacultyPublication.id == pub_id))
    ).first()
    if row is None:
        raise forbidden()
    return row


def row_out(p: FacultyPublication, name: str, unit: str) -> dict[str, Any]:
    return {
        "id": p.id,
        "faculty": {"id": p.faculty_id, "name": name},
        "unit": unit,
        "title": p.title,
        "venue": p.venue,
        "pub_type": p.pub_type,
        "pub_year": p.pub_year,
        "indexing": list(p.indexing),
        "verification": p.verification,
        "updated_at": p.updated_at,
    }


def is_author(principal: Principal, p: FacultyPublication) -> bool:
    return principal.faculty_id == p.faculty_id


def can_check(principal: Principal, p: FacultyPublication) -> bool:
    """The Library, never on its own paper."""
    return can(principal, ENTITY, "update") and not is_author(principal, p)


def view(principal: Principal, row: Any) -> dict[str, Any]:
    p, _, name, unit, checker = row
    return row_out(p, name, unit) | {
        "authors": p.authors,
        "issn_isbn": p.issn_isbn,
        "doi": p.doi,
        "pub_status": p.pub_status,
        "library_note": p.library_note if p.verification == "returned" else None,
        "checked_at": p.checked_at,
        "checked_by": checker,
        "can_edit": is_author(principal, p) and p.verification != "verified",
        "can_check": can_check(principal, p),
    }


async def _tell_library(session: AsyncSession, principal: Principal, count: int) -> None:
    library = [uuid.UUID(h["id"]) for h in await notices.holders(session, None, "library")]
    title = (
        f"{principal.full_name} added {count} papers to verify"
        if count > 1
        else f"{principal.full_name} added a paper to verify"
    )
    notify(
        session,
        [u for u in library if u != principal.user_id],
        "approval_waiting",
        title,
        link="/faculty-publications?verification=waiting",
    )


async def create(
    session: AsyncSession, principal: Principal, data: dict[str, Any]
) -> FacultyPublication:
    pub = await insert(
        session, principal, FacultyPublication(faculty_id=own_faculty(principal), **data)
    )
    await _tell_library(session, principal, 1)
    return pub


async def imported(session: AsyncSession, principal: Principal, count: int) -> None:
    """One notice for the Library however many papers an ORCID import brought in."""
    if count:
        await _tell_library(session, principal, count)


def require_editable(principal: Principal, p: FacultyPublication) -> None:
    if not is_author(principal, p):
        raise forbidden()
    if p.verification == "verified":
        raise ApiError(
            409,
            "already_verified",
            "The Library has verified this paper. Ask the Library to return it to change it.",
        )


async def edit(
    session: AsyncSession, principal: Principal, p: FacultyPublication, changes: dict[str, Any]
) -> None:
    """The author's change; a returned paper goes back to the Library."""
    require_editable(principal, p)
    if p.verification == "returned":
        changes |= {
            "verification": "waiting",
            "library_note": None,
            "checked_at": None,
            "checked_by": None,
        }
        await _tell_library(session, principal, 1)
    await update(session, principal, p, changes)


async def remove(session: AsyncSession, principal: Principal, p: FacultyPublication) -> None:
    require_editable(principal, p)
    await soft_delete(session, principal, p)


async def _check(
    session: AsyncSession,
    principal: Principal,
    p: FacultyPublication,
    author_user_id: uuid.UUID,
    changes: dict[str, Any],
    title: str,
    category: str,
    body: str = "",
) -> None:
    if not can_check(principal, p):
        raise forbidden()
    stamp = {"checked_at": datetime.now(UTC), "checked_by": principal.user_id}
    await update(session, principal, p, changes | stamp)
    link = f"/faculty-publications/{p.id}"
    notify(session, [author_user_id], category, title, body, link=link)


async def verify(
    session: AsyncSession,
    principal: Principal,
    row: Any,
    indexing: list[str],
    doi: str | None,
) -> None:
    """The Library confirms the indexing and DOI it checked; the paper then counts."""
    p, faculty = row[0], row[1]
    if p.verification != "waiting":
        raise ApiError(
            409, "verification_state", "Only a paper waiting for the Library can be verified."
        )
    changes = {"indexing": indexing, "doi": doi, "verification": "verified", "library_note": None}
    await _check(
        session, principal, p, faculty.user_id, changes, f"Verified: {p.title}", "approved"
    )


async def return_(session: AsyncSession, principal: Principal, row: Any, note: str) -> None:
    """Back to the author to correct, waiting or already verified (a later correction)."""
    p, faculty = row[0], row[1]
    if p.verification == "returned":
        raise ApiError(409, "verification_state", "This paper is already with its author.")
    changes = {"verification": "returned", "library_note": note}
    await _check(
        session, principal, p, faculty.user_id, changes, f"Returned: {p.title}", "sent_back", note
    )


async def home(session: AsyncSession, principal: Principal) -> dict[str, int] | None:
    """Home's tiles: papers waiting for the Library to verify (not its own), and a member of
    faculty's papers the Library returned. None for someone neither."""
    checks = can(principal, ENTITY, "update")
    if not (checks or principal.faculty_id) or not await module_enabled(session, "publications"):
        return None
    live = FacultyPublication.deleted_at.is_(None)
    out = {"to_verify": 0, "returned": 0}
    if checks:
        out["to_verify"] = (
            await session.scalar(
                select(func.count()).where(
                    live,
                    FacultyPublication.verification == "waiting",
                    FacultyPublication.faculty_id != principal.faculty_id
                    if principal.faculty_id
                    else true(),
                )
            )
            or 0
        )
    if principal.faculty_id:
        out["returned"] = (
            await session.scalar(
                select(func.count()).where(
                    live,
                    FacultyPublication.faculty_id == principal.faculty_id,
                    FacultyPublication.verification == "returned",
                )
            )
            or 0
        )
    return out
