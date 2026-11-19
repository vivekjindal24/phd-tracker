"""Gates on the committee register (PRD F9): a stage is approved only on top of the stage
before it, and a degree is awarded only to a scholar the record can account for."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.enums import MILESTONE_TYPES
from app.errors import ApiError
from app.models import CommitteeFormation, CommitteeMember, Milestone, ProgressReport, Scholar

MILESTONE_LABELS = {k: k.replace("_", " ").capitalize() for k in MILESTONE_TYPES}


async def _has(session: AsyncSession, *where) -> bool:
    return bool(await session.scalar(select(exists().where(*where))))


async def check_approval(
    session: AsyncSession, principal: Principal, scholar: Scholar, milestone_type: str
) -> None:
    """Called whenever a register entry is about to stand as Approved."""
    at = MILESTONE_TYPES.index(milestone_type)
    if at:
        before = MILESTONE_TYPES[at - 1]
        if not await _has(
            session,
            Milestone.scholar_id == scholar.id,
            Milestone.milestone_type == before,
            Milestone.status == "Approved",
            Milestone.deleted_at.is_(None),
        ):
            raise ApiError(
                422,
                "stage_out_of_order",
                f"{MILESTONE_LABELS[before]} must be approved in the register before "
                f"{MILESTONE_LABELS[milestone_type].lower()}.",
            )
    if milestone_type == "degree_awarded":
        await _check_award(session, principal, scholar.id, scholar.supervisor_id)


async def _check_award(
    session: AsyncSession,
    principal: Principal,
    scholar_id: uuid.UUID,
    supervisor_id: uuid.UUID | None,
) -> None:
    if "research_office" not in principal.office_roles:
        raise ApiError(403, "forbidden", "Only the Research Office records a degree as awarded.")
    missing = []
    if supervisor_id is None:
        missing.append("a supervisor")
    if not await _has(
        session,
        CommitteeMember.formation_id == CommitteeFormation.id,
        CommitteeFormation.scholar_id == scholar_id,
        CommitteeFormation.deleted_at.is_(None),
        CommitteeMember.deleted_at.is_(None),
    ):
        missing.append("a recorded committee")
    if not await _has(
        session,
        ProgressReport.scholar_id == scholar_id,
        ProgressReport.state == "approved",
        ProgressReport.deleted_at.is_(None),
    ):
        missing.append("an approved progress report")
    if missing:
        raise ApiError(
            422,
            "award_not_ready",
            "The degree cannot be awarded yet: this scholar has no " + ", no ".join(missing) + ".",
        )
