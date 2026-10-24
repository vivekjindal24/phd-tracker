"""Admissions (PRD M5, UX Flow 10): an internal record — no applicant portal. Admins manage their
unit's candidates, the research office all of them; a selected candidate converts into a
scholar with a login (the same create_person the Add-person form uses)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import directory, scope
from app.auth import service as auth_service
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import InterviewResult
from app.errors import ApiError, forbidden
from app.models import Admission, OrgUnit, Scholar
from app.modules import require_module
from app.notify import email_configured
from app.rbac import require_perm
from app.schemas import Ref
from app.schemas.administration import (
    AdmissionIn,
    AdmissionOut,
    AdmissionUpdate,
    ConvertIn,
    ConvertOut,
)

router = APIRouter(
    prefix="/admissions", tags=["admissions"], dependencies=[Depends(require_module("admissions"))]
)


def _query(principal: Principal) -> Select:
    return (
        select(Admission, OrgUnit.name, OrgUnit.path)
        .join(OrgUnit, OrgUnit.id == Admission.unit_id)
        .where(
            Admission.deleted_at.is_(None),
            scope.unit_predicate(principal, "admissions", Admission.unit_id),
        )
    )


def _may_write(principal: Principal, unit_path: str) -> bool:
    return "research_office" in principal.office_roles or principal.covers("admin", unit_path)


def _out(row, principal: Principal) -> AdmissionOut:
    a, unit_name, path = row
    return AdmissionOut(
        id=a.id,
        candidate_name=a.candidate_name,
        email=a.email,
        phone=a.phone,
        unit=Ref(id=a.unit_id, name=unit_name),
        entrance_route=a.entrance_route,
        entrance_score=a.entrance_score,
        interview_date=a.interview_date,
        interview_result=a.interview_result,
        admitted_on=a.admitted_on,
        scholar_id=a.scholar_id,
        can_edit=_may_write(principal, path),
    )


async def _writable(session: AsyncSession, principal: Principal, admission_id: uuid.UUID):
    row = (await session.execute(_query(principal).where(Admission.id == admission_id))).first()
    if row is None or not _may_write(principal, row[2]):
        raise forbidden()
    return row


@router.get("", response_model=list[AdmissionOut])
async def list_admissions(
    unit_id: uuid.UUID | None = None,
    interview_result: InterviewResult | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    principal: Principal = Depends(require_perm("admissions", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[AdmissionOut]:
    stmt = _query(principal)
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Admission.unit_id.in_(scope.subtree_unit_ids((path,))))
    if interview_result:
        stmt = stmt.where(Admission.interview_result == interview_result)
    rows = await session.execute(stmt.order_by(Admission.created_at.desc()).limit(limit))
    return [_out(r, principal) for r in rows]


@router.post("", response_model=AdmissionOut, status_code=201)
async def create_admission(
    body: AdmissionIn,
    principal: Principal = Depends(require_perm("admissions", "create")),
    session: AsyncSession = Depends(get_session),
) -> AdmissionOut:
    if not _may_write(principal, await scope.unit_path(session, body.unit_id)):
        raise forbidden()
    a = await insert(session, principal, Admission(**body.model_dump()))
    await session.commit()
    return _out(await _writable(session, principal, a.id), principal)


@router.patch("/{admission_id}", response_model=AdmissionOut)
async def update_admission(
    admission_id: uuid.UUID,
    body: AdmissionUpdate,
    principal: Principal = Depends(require_perm("admissions", "update")),
    session: AsyncSession = Depends(get_session),
) -> AdmissionOut:
    a, *_ = await _writable(session, principal, admission_id)
    if a.scholar_id is not None:
        raise ApiError(422, "already_converted", "This candidate is already a scholar.")
    await update(session, principal, a, body.model_dump(exclude_unset=True))
    await session.commit()
    return _out(await _writable(session, principal, admission_id), principal)


@router.delete("/{admission_id}", status_code=204)
async def delete_admission(
    admission_id: uuid.UUID,
    principal: Principal = Depends(require_perm("admissions", "delete")),
    session: AsyncSession = Depends(get_session),
) -> None:
    a, *_ = await _writable(session, principal, admission_id)
    if a.scholar_id is not None:
        raise ApiError(422, "already_converted", "A converted admission stays on record.")
    await soft_delete(session, principal, a)
    await session.commit()


@router.post("/{admission_id}/convert", response_model=ConvertOut)
async def convert(
    admission_id: uuid.UUID,
    body: ConvertIn,
    principal: Principal = Depends(require_perm("admissions", "convert")),
    session: AsyncSession = Depends(get_session),
) -> ConvertOut:
    """Selected candidate -> scholar profile + login (PRD M5)."""
    a, *_ = await _writable(session, principal, admission_id)
    if a.scholar_id is not None:
        raise ApiError(422, "already_converted", "This candidate is already a scholar.")
    if a.interview_result != "selected":
        raise ApiError(422, "not_selected", "Only selected candidates become scholars.")
    if body.password is None and not email_configured():
        raise auth_service.EMAIL_NOT_CONFIGURED
    user = await directory.create_person(
        session,
        principal,
        email=a.email,
        full_name=a.candidate_name,
        password_hash=auth_service.hash_password(body.password) if body.password else None,
        scholar=Scholar(
            unit_id=a.unit_id,
            roll_number=body.roll_number,
            research_title=body.research_title,
            admission_date=a.admitted_on,
        ),
        authorised_by_admission=True,
    )
    scholar_id = await session.scalar(select(Scholar.id).where(Scholar.user_id == user.id))
    await update(session, principal, a, {"scholar_id": scholar_id})
    if body.password is not None:
        await session.commit()
        return ConvertOut(scholar_id=scholar_id, invitation_sent=False)
    raw = await auth_service.issue_password_link(session, user.id, "invite")
    await session.commit()
    try:
        await auth_service.email_password_link(user, raw, "invite")
    except Exception as exc:
        raise ApiError(
            502,
            "email_failed",
            f"The scholar was created, but the invitation email failed: {exc}. "
            "Send it again from their profile.",
        ) from exc
    return ConvertOut(scholar_id=scholar_id, invitation_sent=True)
