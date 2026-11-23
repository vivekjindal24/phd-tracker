"""Faculty publications (PRD M1, faculty_papers.py): the author records and corrects them; the
Library verifies or returns them. Part of the publications module."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app import doi, faculty_papers, orcid, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.enums import VERIFICATIONS, Indexing, Verification
from app.models import Faculty, FacultyPublication, User
from app.modules import require_module
from app.schemas.research import (
    DoiDetails,
    DoiImportIn,
    DoiImportOut,
    FacultyPublicationRow,
    FacultyPublicationView,
    OrcidWork,
    PublicationIn,
    PublicationUpdate,
    ReturnIn,
    VerificationIn,
)
from app.sorting import Sort, ordered, page_of, ranked

router = APIRouter(
    prefix="/faculty-publications",
    tags=["faculty publications"],
    dependencies=[Depends(require_module("publications"))],
)


def _owner(principal: Principal) -> dict[str, uuid.UUID]:
    return {"faculty_id": faculty_papers.own_faculty(principal)}


@router.get("", response_model=list[FacultyPublicationRow])
async def list_faculty_publications(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    faculty_id: uuid.UUID | None = None,
    verification: Verification | None = None,
    pub_year: int | None = Query(default=None, ge=1950, le=2100),
    indexing: Indexing | None = None,
    sort: Sort = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    faculty_papers.require_reader(principal)
    stmt = faculty_papers.base_query(principal)
    if q:
        stmt = stmt.where(
            or_(
                FacultyPublication.title.icontains(q, autoescape=True),
                FacultyPublication.venue.icontains(q, autoescape=True),
                User.full_name.icontains(q, autoescape=True),
            )
        )
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Faculty.unit_id.in_(scope.subtree_unit_ids((path,))))
    if faculty_id:
        stmt = stmt.where(FacultyPublication.faculty_id == faculty_id)
    if verification:
        stmt = stmt.where(FacultyPublication.verification == verification)
    if pub_year:
        stmt = stmt.where(FacultyPublication.pub_year == pub_year)
    if indexing:
        stmt = stmt.where(FacultyPublication.indexing.contains([indexing]))
    columns = {
        "title": FacultyPublication.title,
        "faculty": User.full_name,
        "venue": FacultyPublication.venue,
        "verification": ranked(FacultyPublication.verification, VERIFICATIONS),
    }
    default = [FacultyPublication.pub_year.desc(), FacultyPublication.updated_at.desc()]
    stmt = ordered(stmt, sort, columns, default, FacultyPublication.id)
    rows = await page_of(session, response, stmt, limit, offset)
    return [faculty_papers.row_out(p, name, unit) for p, _, name, unit, _ in rows]


@router.get("/doi", response_model=DoiDetails)
async def look_up_doi(
    q: str = Query(min_length=1, max_length=300),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The author's DOI, filled from Crossref; nothing is saved until they submit the form."""
    owner = _owner(principal)
    found = await doi.lookup(q)
    have = await orcid.recorded_dois(session, FacultyPublication, owner)
    return found | {"already_recorded": found["doi"].lower() in have}


@router.get("/orcid", response_model=list[OrcidWork])
async def orcid_works(
    q: str = Query(min_length=1, max_length=100),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    have = await orcid.recorded_dois(session, FacultyPublication, _owner(principal))
    return [
        w | {"already_recorded": bool(w["doi"]) and w["doi"].lower() in have}
        for w in await orcid.works(q)
    ]


@router.post("/import", response_model=DoiImportOut)
async def import_faculty_publications(
    body: DoiImportIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Each chosen DOI, filled from Crossref, goes to the Library to verify."""
    out = await orcid.import_dois(
        session, principal, body.dois, FacultyPublication, _owner(principal)
    )
    await faculty_papers.imported(session, principal, len(out["created"]))
    await session.commit()
    return out


@router.post("", response_model=FacultyPublicationView, status_code=201)
async def create_faculty_publication(
    body: PublicationIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    pub = await faculty_papers.create(session, principal, body.model_dump())
    await session.commit()
    return await _view(session, principal, pub.id)


async def _view(session: AsyncSession, principal: Principal, pub_id: uuid.UUID) -> dict:
    row = await faculty_papers.get_or_403(session, principal, pub_id)
    return faculty_papers.view(principal, row)


@router.get("/{pub_id}", response_model=FacultyPublicationView)
async def get_faculty_publication(
    pub_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _view(session, principal, pub_id)


@router.patch("/{pub_id}", response_model=FacultyPublicationView)
async def update_faculty_publication(
    pub_id: uuid.UUID,
    body: PublicationUpdate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await faculty_papers.get_or_403(session, principal, pub_id)
    await faculty_papers.edit(session, principal, row[0], body.model_dump(exclude_unset=True))
    await session.commit()
    return await _view(session, principal, pub_id)


@router.delete("/{pub_id}", status_code=204)
async def delete_faculty_publication(
    pub_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await faculty_papers.get_or_403(session, principal, pub_id)
    await faculty_papers.remove(session, principal, row[0])
    await session.commit()


@router.post("/{pub_id}/verify", response_model=FacultyPublicationView)
async def verify_faculty_publication(
    pub_id: uuid.UUID,
    body: VerificationIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await faculty_papers.get_or_403(session, principal, pub_id)
    await faculty_papers.verify(session, principal, row, body.indexing, body.doi)
    await session.commit()
    return await _view(session, principal, pub_id)


@router.post("/{pub_id}/return", response_model=FacultyPublicationView)
async def return_faculty_publication(
    pub_id: uuid.UUID,
    body: ReturnIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await faculty_papers.get_or_403(session, principal, pub_id)
    await faculty_papers.return_(session, principal, row, body.note)
    await session.commit()
    return await _view(session, principal, pub_id)
