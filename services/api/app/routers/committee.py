"""Committees in versions (PRD F9b): a scholar's Research Advisory Committee, and a
department's research committee. A record, not an approval step: a scholar's committee is
kept by an admin over the scholar's unit or the Research Office, like the register; a
department's by an admin over that department or the Research Office. Only the current
(latest) version changes its members, roles and seats; on an earlier one, only the wording
may be corrected (its date, order number and notes, an outside expert's name or institution)."""

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import committee, scope
from app.auth.principal import Principal
from app.crud import insert, soft_delete, update
from app.db import get_session
from app.enums import ADVISORY_ROLES, DEPARTMENT_ROLES
from app.errors import ApiError, forbidden
from app.models import CommitteeFormation, CommitteeMember, Faculty, OrgUnit, Scholar, Settings
from app.rbac import require_perm
from app.schemas.administration import (
    CommitteeMemberIn,
    CommitteeMemberPatch,
    CommitteeView,
    FormationIn,
)

router = APIRouter(tags=["committee"])
ENTITY = "committee_members"
ADVISORY_TITLE = "Research Advisory Committee"


@dataclass(frozen=True)
class Owner:
    """Whose committee: a scholar's (advisory) or a unit's (department)."""

    scholar: Scholar | None = None
    unit: OrgUnit | None = None

    @property
    def clause(self) -> ColumnElement[bool]:
        if self.scholar is not None:
            return CommitteeFormation.scholar_id == self.scholar.id
        assert self.unit is not None
        return CommitteeFormation.unit_id == self.unit.id


async def _keeps(session: AsyncSession, principal: Principal, owner: Owner) -> bool:
    if owner.scholar is not None:
        return await scope.can_record(session, principal, owner.scholar)
    assert owner.unit is not None
    return "research_office" in principal.office_roles or principal.covers("admin", owner.unit.path)


async def _view(session: AsyncSession, principal: Principal, owner: Owner) -> dict[str, Any]:
    if owner.scholar is not None:
        title, convener = ADVISORY_TITLE, await committee.convener(session, owner.scholar)
    else:
        title = await session.scalar(select(Settings.department_committee_name))
        convener = None
    keeps = await _keeps(session, principal, owner)
    formations = await committee.formations(session, owner.clause)
    if not keeps:  # outside members' emails reach only those who keep the committee
        for f in formations:
            for m in f["members"]:
                m["email"] = None
    return {"title": title, "convener": convener, "formations": formations, "can_manage": keeps}


async def _readable_unit(session: AsyncSession, principal: Principal, unit_id: uuid.UUID) -> Owner:
    unit = await session.scalar(
        select(OrgUnit).where(
            OrgUnit.id == unit_id,
            OrgUnit.deleted_at.is_(None),
            scope.org_tree_predicate(principal),
        )
    )
    if unit is None:
        raise forbidden()
    return Owner(unit=unit)


async def _kept(session: AsyncSession, principal: Principal, owner: Owner) -> Owner:
    if not await _keeps(session, principal, owner):
        raise forbidden()
    return owner


async def _owner_of(
    session: AsyncSession, principal: Principal, formation: CommitteeFormation
) -> Owner:
    """The committee a version belongs to, if the caller keeps it."""
    if formation.scholar_id is not None:
        scholar = await scope.get_scholar_or_403(session, principal, formation.scholar_id, ENTITY)
        return await _kept(session, principal, Owner(scholar=scholar))
    assert formation.unit_id is not None
    return await _kept(
        session, principal, await _readable_unit(session, principal, formation.unit_id)
    )


async def _formation(
    session: AsyncSession, principal: Principal, formation_id: uuid.UUID
) -> tuple[Owner, CommitteeFormation]:
    """Any live version of a committee the caller keeps."""
    formation = await session.scalar(
        select(CommitteeFormation).where(
            CommitteeFormation.id == formation_id, CommitteeFormation.deleted_at.is_(None)
        )
    )
    if formation is None:
        raise forbidden()
    return await _owner_of(session, principal, formation), formation


async def _current_formation(
    session: AsyncSession, principal: Principal, formation_id: uuid.UUID
) -> tuple[Owner, CommitteeFormation]:
    """A version whose members may change: it must be the committee's current one."""
    owner, formation = await _formation(session, principal, formation_id)
    latest = await committee.current(session, owner.clause)
    if latest is None or latest.id != formation.id:
        raise ApiError(
            409, "formation_superseded", "An earlier committee is history; change the current one."
        )
    return owner, formation


async def _live_member(session: AsyncSession, member_id: uuid.UUID) -> CommitteeMember:
    row = await session.scalar(
        select(CommitteeMember).where(
            CommitteeMember.id == member_id, CommitteeMember.deleted_at.is_(None)
        )
    )
    if row is None:
        raise forbidden()
    return row


def _out_of_order() -> ApiError:
    return ApiError(
        422, "formation_out_of_order", "The versions must stay in order of the date formed."
    )


def _check_role_and_seat(owner: Owner, role: str, seat: str | None, is_scholar: bool) -> None:
    """An advisory committee takes chairperson / member / VC nominee and no seats; a
    department's takes chairperson / secretary / member, each in a seat, a scholar in the
    scholar's seat and nobody else there."""
    if owner.scholar is not None:
        if role not in ADVISORY_ROLES or seat is not None or is_scholar:
            raise ApiError(
                422,
                "role_not_allowed",
                "An advisory committee takes a chairperson, members and a VC nominee, "
                "faculty or outside experts, without seats.",
            )
        return
    if role not in DEPARTMENT_ROLES:
        raise ApiError(
            422,
            "role_not_allowed",
            "A department's committee takes a chairperson, a secretary and members.",
        )
    if seat is None or (seat == "scholar") != is_scholar:
        raise ApiError(
            422, "seat_mismatch", "Give each member a seat; a scholar sits in the scholar's seat."
        )


async def _check_person(
    session: AsyncSession, owner: Owner, formation: CommitteeFormation, body: CommitteeMemberIn
) -> None:
    if body.faculty_id is not None:
        if owner.scholar is not None and body.faculty_id in (
            owner.scholar.supervisor_id,
            formation.secretary_id,
        ):
            raise ApiError(
                409, "supervisor_is_convener", "The supervisor is already the secretary."
            )
        known = await session.scalar(
            select(Faculty.id).where(Faculty.id == body.faculty_id, Faculty.deleted_at.is_(None))
        )
        if known is None:
            raise ApiError(422, "faculty_not_found", "This faculty member does not exist.")
    if body.scholar_member_id is not None:
        assert owner.unit is not None  # _check_role_and_seat refused it on an advisory one
        here = await session.scalar(
            select(Scholar.id).where(
                Scholar.id == body.scholar_member_id,
                Scholar.deleted_at.is_(None),
                Scholar.unit_id.in_(scope.subtree_unit_ids((owner.unit.path,))),
            )
        )
        if here is None:
            raise ApiError(
                422, "scholar_not_in_unit", "The scholar must belong to this department."
            )


async def _form(
    session: AsyncSession, principal: Principal, owner: Owner, body: FormationIn
) -> dict[str, Any]:
    """Form the committee, or re-form it: the new version starts as a copy of the current
    members, to be changed from there."""
    previous = await committee.current(session, owner.clause)
    if previous is not None and body.formed_on < previous.formed_on:
        raise _out_of_order()
    formation = await insert(
        session,
        principal,
        CommitteeFormation(
            scholar_id=owner.scholar.id if owner.scholar else None,
            unit_id=owner.unit.id if owner.unit else None,
            secretary_id=owner.scholar.supervisor_id if owner.scholar else None,
            **body.model_dump(),
        ),
    )
    if previous is not None:
        for m in await session.scalars(
            select(CommitteeMember).where(
                CommitteeMember.formation_id == previous.id, CommitteeMember.deleted_at.is_(None)
            )
        ):
            await insert(
                session,
                principal,
                CommitteeMember(
                    formation_id=formation.id,
                    faculty_id=m.faculty_id,
                    scholar_member_id=m.scholar_member_id,
                    name=m.name,
                    institution=m.institution,
                    email=m.email,
                    role=m.role,
                    seat=m.seat,
                ),
            )
    await session.commit()
    return await _view(session, principal, owner)


@router.get("/scholars/{scholar_id}/committee", response_model=CommitteeView)
async def get_committee(
    scholar_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    return await _view(session, principal, Owner(scholar=scholar))


@router.post("/scholars/{scholar_id}/committee/formations", response_model=CommitteeView)
async def form_committee(
    scholar_id: uuid.UUID,
    body: FormationIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    scholar = await scope.get_scholar_or_403(session, principal, scholar_id, ENTITY)
    return await _form(
        session, principal, await _kept(session, principal, Owner(scholar=scholar)), body
    )


@router.get("/org-units/{unit_id}/committee", response_model=CommitteeView)
async def get_department_committee(
    unit_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await _view(session, principal, await _readable_unit(session, principal, unit_id))


@router.post("/org-units/{unit_id}/committee/formations", response_model=CommitteeView)
async def form_department_committee(
    unit_id: uuid.UUID,
    body: FormationIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    owner = await _kept(session, principal, await _readable_unit(session, principal, unit_id))
    return await _form(session, principal, owner, body)


@router.patch("/committee-formations/{formation_id}", response_model=CommitteeView)
async def correct_formation(
    formation_id: uuid.UUID,
    body: FormationIn,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Correct any version's date, order number or notes; it stays between its neighbours."""
    owner, formation = await _formation(session, principal, formation_id)
    versions = await committee.versions(session, owner.clause)
    at = versions.index(formation)  # newest first
    newer = versions[at - 1].formed_on if at > 0 else None
    older = versions[at + 1].formed_on if at + 1 < len(versions) else None
    if (older is not None and body.formed_on < older) or (
        newer is not None and body.formed_on > newer
    ):
        raise _out_of_order()
    await update(session, principal, formation, body.model_dump())
    await session.commit()
    return await _view(session, principal, owner)


@router.delete("/committee-formations/{formation_id}", response_model=CommitteeView)
async def withdraw_formation(
    formation_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Withdraw a version recorded by mistake; the one before it is current again."""
    owner, formation = await _current_formation(session, principal, formation_id)
    for m in await session.scalars(
        select(CommitteeMember).where(
            CommitteeMember.formation_id == formation.id, CommitteeMember.deleted_at.is_(None)
        )
    ):
        await soft_delete(session, principal, m)
    await soft_delete(session, principal, formation)
    await session.commit()
    return await _view(session, principal, owner)


@router.post("/committee-formations/{formation_id}/members", response_model=CommitteeView)
async def add_member(
    formation_id: uuid.UUID,
    body: CommitteeMemberIn,
    principal: Principal = Depends(require_perm(ENTITY, "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    owner, formation = await _current_formation(session, principal, formation_id)
    _check_role_and_seat(owner, body.role, body.seat, body.scholar_member_id is not None)
    await _check_person(session, owner, formation, body)
    await insert(
        session, principal, CommitteeMember(formation_id=formation.id, **body.model_dump())
    )
    await session.commit()
    return await _view(session, principal, owner)


@router.patch("/committee-members/{member_id}", response_model=CommitteeView)
async def correct_member(
    member_id: uuid.UUID,
    body: CommitteeMemberPatch,
    principal: Principal = Depends(require_perm(ENTITY, "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """A role or seat changes on the current version only; an outside expert's name or
    institution may be corrected on any version (others' come from the directory)."""
    row = await _live_member(session, member_id)
    changes = body.model_dump(exclude_none=True)
    if body.role is not None or body.seat is not None:
        owner, _ = await _current_formation(session, principal, row.formation_id)
        _check_role_and_seat(
            owner,
            body.role or row.role,
            body.seat or row.seat,
            row.scholar_member_id is not None,
        )
    else:
        owner, _ = await _formation(session, principal, row.formation_id)
    if row.name is None and (body.name or body.institution or body.email):
        raise ApiError(422, "directory_name", "A member's name and unit come from the directory.")
    await update(session, principal, row, changes)
    await session.commit()
    return await _view(session, principal, owner)


@router.delete("/committee-members/{member_id}", response_model=CommitteeView)
async def remove_member(
    member_id: uuid.UUID,
    principal: Principal = Depends(require_perm(ENTITY, "delete")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await _live_member(session, member_id)
    owner, _ = await _current_formation(session, principal, row.formation_id)
    await soft_delete(session, principal, row)
    await session.commit()
    return await _view(session, principal, owner)
