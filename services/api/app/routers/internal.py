"""Read models for the export service (ARCHITECTURE.md §2, SECURITY.md §6). Same JWT, same
scope as every other route: the export service forwards the caller's token verbatim, so a
PDF can only ever contain what that person may already see."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import items, scope
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.enums import MilestoneStatus, MilestoneType
from app.models import Faculty, Milestone, OrgUnit, Scholar, User
from app.rbac import require_perm

router = APIRouter(prefix="/internal", tags=["internal"])
REGISTER_LIMIT = 2000


async def _university(session: AsyncSession) -> str:
    return (
        await session.scalar(
            select(OrgUnit.name).where(OrgUnit.parent_id.is_(None), OrgUnit.deleted_at.is_(None))
        )
        or "University"
    )


@router.get("/reports/{report_id}/export-view")
async def report_export_view(
    report_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await items.load_ctx(session, principal, "progress_report", report_id)
    view = await items.view(session, principal, ctx)
    sup_name = None
    if ctx.scholar.supervisor_id:
        sup_name = await session.scalar(
            select(User.full_name)
            .join(Faculty, Faculty.user_id == User.id)
            .where(Faculty.id == ctx.scholar.supervisor_id)
        )
    unit = await session.scalar(select(OrgUnit.name).where(OrgUnit.id == ctx.scholar.unit_id))
    return {
        "university": await _university(session),
        "unit": unit,
        "scholar": view["scholar"]["name"],
        "roll_number": ctx.scholar.roll_number,
        "supervisor": sup_name,
        "period": view["content"]["period"],
        "report_year": view["content"]["report_year"],
        "summary": view["content"]["summary"],
        "state": view["state"],
        "submitted_at": view["submitted_at"],
        "approved_at": view["approved_at"],
        "history": view["history"],
        "generated_at": datetime.now(UTC),
        "generated_by": principal.full_name,
    }


@router.get("/register-view")
async def register_export_view(
    unit_id: uuid.UUID | None = None,
    milestone_type: MilestoneType | None = None,
    status: MilestoneStatus | None = None,
    principal: Principal = Depends(require_perm("milestones", "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ScholarUser = aliased(User)
    stmt = (
        select(Milestone, Scholar.roll_number, ScholarUser.full_name, OrgUnit.name)
        .join(Scholar, Scholar.id == Milestone.scholar_id)
        .join(ScholarUser, ScholarUser.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .where(
            Milestone.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, "milestones"),
        )
    )
    unit_name = None
    if unit_id:
        path = await scope.unit_path(session, unit_id)
        stmt = stmt.where(Scholar.unit_id.in_(scope.subtree_unit_ids((path,))))
        unit_name = await session.scalar(select(OrgUnit.name).where(OrgUnit.id == unit_id))
    if milestone_type:
        stmt = stmt.where(Milestone.milestone_type == milestone_type)
    if status:
        stmt = stmt.where(Milestone.status == status)
    rows = await session.execute(
        stmt.order_by(Milestone.resolution_date.desc().nulls_last(), ScholarUser.full_name).limit(
            REGISTER_LIMIT
        )
    )
    return {
        "university": await _university(session),
        "unit": unit_name,
        "filters": {"milestone_type": milestone_type, "status": status},
        "rows": [
            {
                "scholar": name,
                "roll_number": roll,
                "unit": unit,
                "milestone_type": m.milestone_type,
                "status": m.status,
                "approval_body": m.approval_body,
                "resolution_number": m.resolution_number,
                "resolution_date": m.resolution_date,
                "notes": m.notes,
            }
            for m, roll, name, unit in rows
        ],
        "generated_at": datetime.now(UTC),
        "generated_by": principal.full_name,
    }
