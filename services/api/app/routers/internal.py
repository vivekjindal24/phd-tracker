"""Read models for the export service (ARCHITECTURE.md §2, SECURITY.md §6). Same JWT, same
scope as every other route: the export service forwards the caller's token verbatim, so a
PDF can only ever contain what that person may already see."""

import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import apr, branding, certificate, committee, grants, items, naac, reviews, scope
from app.auth.deps import current_principal, current_reviewer
from app.auth.principal import Principal
from app.db import get_session
from app.enums import MilestoneStatus, MilestoneType
from app.errors import ApiError, forbidden
from app.models import Faculty, FileRow, Milestone, OrgUnit, Scholar, User
from app.rbac import require_perm
from app.schemas.research import ReviewCopyView

router = APIRouter(prefix="/internal", tags=["internal"])
REGISTER_LIMIT = 2000
NAAC_MAX_YEARS = 10


@router.get("/reports/{report_id}/export-view")
async def report_export_view(
    report_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await items.load_ctx(session, principal, "progress_report", report_id)
    view = await items.view(session, principal, ctx)
    sup_name = await committee.convener(session, ctx.scholar)
    unit = await session.scalar(select(OrgUnit.name).where(OrgUnit.id == ctx.scholar.unit_id))
    return {
        **await branding.export_fields(session),
        "unit": unit,
        "scholar": view["scholar"]["name"],
        "roll_number": ctx.scholar.roll_number,
        "supervisor": sup_name,
        "committee": [
            f"{m['name']} ({m['institution']})"
            for m in await committee.members(session, ctx.scholar)
        ],
        "period": view["content"]["period"],
        "report_year": view["content"]["report_year"],
        "summary": view["content"]["summary"],
        "sections": view["content"]["sections"],
        "activity": await apr.activity(
            session, ctx.scholar, view["content"]["report_year"], view["content"]["period"]
        ),
        "files": list(
            await session.scalars(
                select(FileRow.file_name)
                .where(
                    FileRow.table_name == "progress_reports",
                    FileRow.record_id == report_id,
                    FileRow.status == "ready",
                    FileRow.deleted_at.is_(None),
                )
                .order_by(FileRow.created_at)
            )
        ),
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
        **await branding.export_fields(session),
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


@router.get("/naac/{sheet}")
async def naac_view(
    sheet: Literal["projects", "scholars", "publications", "books"],
    from_year: int = Query(ge=2000, le=2100),
    to_year: int = Query(ge=2000, le=2100),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Academic years from_year-… to to_year-…, university wide (PRD M9)."""
    if not (principal.is_root_admin or principal.reads_all):
        raise forbidden()
    if not 0 <= to_year - from_year < NAAC_MAX_YEARS:
        raise ApiError(422, "invalid_years", f"Choose up to {NAAC_MAX_YEARS} academic years.")
    if sheet in naac.SHEET_MODULES:
        await grants.require_module(session, naac.SHEET_MODULES[sheet])
    title, columns, build = naac.SHEETS[sheet]
    period = (
        date(from_year, naac.AY_START_MONTH, 1),
        date(to_year + 1, naac.AY_START_MONTH - 1, 30),
    )
    return {
        **await branding.export_fields(session),
        "title": title,
        "columns": columns,
        "rows": await build(session, period),
        "generated_at": datetime.now(UTC),
        "generated_by": principal.full_name,
    }


@router.get("/certificates/{certificate_id}/export-view")
async def certificate_export_view(
    certificate_id: uuid.UUID,
    principal: Principal = Depends(current_principal),  # whoever may read the thesis
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return {
        **await branding.export_fields(session),
        **await certificate.export_view(session, principal, certificate_id),
        "generated_at": datetime.now(UTC),
        "generated_by": principal.full_name,
    }


@router.get("/reviews/{review_id}/copy", response_model=ReviewCopyView)
async def review_copy(
    review_id: uuid.UUID,
    download: bool = False,
    principal: Principal = Depends(current_reviewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """A fresh traceable copy of the thesis; the export service stamps its code on each page."""
    await grants.require_module(session, "documents")
    view = await reviews.issue_copy(session, principal, review_id, download=download)
    await session.commit()
    return view


@router.get("/ucs/{uc_id}/export-view")
async def uc_export_view(
    uc_id: uuid.UUID,
    principal: Principal = Depends(current_principal),  # whoever sees the project's ledger
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    uc, _ = await grants.uc_or_403(session, principal, uc_id)
    project, _ = await grants.project_or_403(session, principal, uc.project_id, ledger=True)
    pi = await session.scalar(
        select(User.full_name)
        .join(Faculty, Faculty.user_id == User.id)
        .where(Faculty.id == project.pi_id)
    )
    unit = await session.scalar(select(OrgUnit.name).where(OrgUnit.id == project.unit_id))
    return {
        **await branding.export_fields(session),
        "unit": unit,
        "title": project.title,
        "agency": project.agency,
        "sanction_number": project.sanction_number,
        "amount_sanctioned": project.amount_sanctioned,
        "pi": pi,
        "period_start": uc.period_start,
        "period_end": uc.period_end,
        **await grants.uc_figures(session, uc),
        "generated_at": datetime.now(UTC),
        "generated_by": principal.full_name,
    }
