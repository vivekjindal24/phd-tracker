"""Patents (PRD M10, patents.py): the author records and updates them; the office the university
chose verifies or returns them. Module `patents`."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app import patents, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.enums import PATENT_STATUSES, VERIFICATIONS, PatentStatus, Verification
from app.models import Faculty, Patent, Scholar, User
from app.modules import require_module
from app.schemas.research import PatentIn, PatentRow, PatentView, ReturnIn
from app.sorting import Sort, ordered, page_of, ranked

router = APIRouter(
    prefix="/patents", tags=["patents"], dependencies=[Depends(require_module("patents"))]
)


@router.get("", response_model=list[PatentRow])
async def list_patents(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    verification: Verification | None = None,
    patent_status: PatentStatus | None = None,
    mine: bool = False,
    sort: Sort = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    patents.require_reader(principal)
    stmt = patents.base_query(principal)
    if q:
        stmt = stmt.where(
            or_(
                Patent.title.icontains(q, autoescape=True),
                Patent.application_number.icontains(q, autoescape=True),
                Patent.inventors.icontains(q, autoescape=True),
                User.full_name.icontains(q, autoescape=True),
            )
        )
    if unit_id:
        units = scope.subtree_unit_ids((await scope.unit_path(session, unit_id),))
        stmt = stmt.where(or_(Faculty.unit_id.in_(units), Scholar.unit_id.in_(units)))
    if mine:
        own = [Patent.faculty_id == principal.faculty_id] if principal.faculty_id else []
        own += [Patent.scholar_id == principal.scholar_id] if principal.scholar_id else []
        stmt = stmt.where(or_(*own)) if own else stmt.where(Patent.id.is_(None))
    if verification:
        stmt = stmt.where(Patent.verification == verification)
    if patent_status:
        stmt = stmt.where(Patent.patent_status == patent_status)
    columns = {
        "title": Patent.title,
        "owner": User.full_name,
        "filed_on": Patent.filed_on,
        "status": ranked(Patent.patent_status, PATENT_STATUSES),
        "verification": ranked(Patent.verification, VERIFICATIONS),
    }
    default = [Patent.filed_on.desc(), Patent.updated_at.desc()]
    stmt = ordered(stmt, sort, columns, default, Patent.id)
    rows = await page_of(session, response, stmt, limit, offset)
    return [patents.row_out(p, name, unit) for p, name, _, unit, _ in rows]


@router.post("", response_model=PatentView, status_code=201)
async def create_patent(
    body: PatentIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    patent = await patents.create(session, principal, body.model_dump())
    await session.commit()
    return await _view(session, principal, patent.id)


async def _view(session: AsyncSession, principal: Principal, patent_id: uuid.UUID) -> dict:
    return await patents.view(
        session, principal, await patents.get_or_403(session, principal, patent_id)
    )


@router.get("/{patent_id}", response_model=PatentView)
async def get_patent(
    patent_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _view(session, principal, patent_id)


@router.put("/{patent_id}", response_model=PatentView)
async def update_patent(
    patent_id: uuid.UUID,
    body: PatentIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The whole record, so the status and its dates stay consistent (PatentIn checks them)."""
    row = await patents.get_or_403(session, principal, patent_id)
    await patents.edit(session, principal, row[0], body.model_dump())
    await session.commit()
    return await _view(session, principal, patent_id)


@router.delete("/{patent_id}", status_code=204)
async def delete_patent(
    patent_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = await patents.get_or_403(session, principal, patent_id)
    await patents.remove(session, principal, row[0])
    await session.commit()


@router.post("/{patent_id}/verify", response_model=PatentView)
async def verify_patent(
    patent_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await patents.verify(
        session, principal, await patents.get_or_403(session, principal, patent_id)
    )
    await session.commit()
    return await _view(session, principal, patent_id)


@router.post("/{patent_id}/return", response_model=PatentView)
async def return_patent(
    patent_id: uuid.UUID,
    body: ReturnIn,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await patents.get_or_403(session, principal, patent_id)
    await patents.return_(session, principal, row, body.note)
    await session.commit()
    return await _view(session, principal, patent_id)
