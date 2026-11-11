"""Six-monthly progress reports (PRD F8, UX Flow 1). Workflow actions live on /items."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import apr, items, scope, workflow
from app.auth.principal import Principal
from app.crud import insert, update
from app.db import get_session
from app.enums import ItemState
from app.errors import ApiError
from app.models import OrgUnit, ProgressReport, Scholar, User
from app.rbac import require_perm
from app.schemas import ItemView, PeriodActivity, ReportIn, ReportRow, ReportUpdate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportRow])
async def list_reports(
    q: str | None = Query(default=None, max_length=100),
    unit_id: uuid.UUID | None = None,
    state: ItemState | None = None,
    scholar_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_perm("progress_reports", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(ProgressReport, Scholar, User.full_name)
        .join(Scholar, Scholar.id == ProgressReport.scholar_id)
        .join(User, User.id == Scholar.user_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .where(
            ProgressReport.deleted_at.is_(None),
            scope.scholar_predicate(principal, "progress_reports"),
        )
    )
    stmt = await scope.narrow_to_scholars(session, stmt, q, unit_id)
    if state:
        stmt = stmt.where(ProgressReport.state == state)
    if scholar_id:
        stmt = stmt.where(ProgressReport.scholar_id == scholar_id)
    rows = await session.execute(
        stmt.order_by(
            ProgressReport.report_year.desc(), ProgressReport.period.desc(), User.full_name
        )
        .limit(limit)
        .offset(offset)
    )
    out = []
    for r, scholar, name in rows:
        kind = r.chain_snapshot[r.current_step]["kind"] if r.current_step is not None else None
        out.append(
            {
                "id": r.id,
                "scholar": {"id": scholar.id, "name": name},
                "report_year": r.report_year,
                "period": r.period,
                "state": r.state,
                "waiting_on": workflow.STEP_LABELS[kind] if kind else None,
                "submitted_at": r.submitted_at,
                "approved_at": r.approved_at,
                "updated_at": r.updated_at,
            }
        )
    return out


@router.post("", response_model=ItemView, status_code=201)
async def create_report(
    body: ReportIn,
    principal: Principal = Depends(require_perm("progress_reports", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if principal.scholar_id is None:
        raise ApiError(403, "forbidden", "Only scholars write their own progress reports.")
    report = await insert(
        session,
        principal,
        ProgressReport(
            scholar_id=principal.scholar_id,
            report_year=body.report_year,
            period=body.period,
            summary=body.summary,
            sections=await apr.clean_sections(session, [s.model_dump() for s in body.sections]),
        ),
    )
    await session.commit()
    ctx = await items.load_ctx(session, principal, "progress_report", report.id)
    return await items.view(session, principal, ctx)


@router.patch("/{report_id}", response_model=ItemView)
async def update_report(
    report_id: uuid.UUID,
    body: ReportUpdate,
    principal: Principal = Depends(require_perm("progress_reports", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await items.load_ctx(session, principal, "progress_report", report_id, lock=True)
    workflow.assert_editable(principal, ctx)  # author only, draft or sent back only
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "sections" in changes:
        changes["sections"] = await apr.clean_sections(session, changes["sections"])
    await update(session, principal, ctx.item, changes)
    await session.commit()
    return await items.view(session, principal, ctx)


@router.get("/{report_id}/activity", response_model=PeriodActivity)
async def report_activity(
    report_id: uuid.UUID,
    principal: Principal = Depends(require_perm("progress_reports", "read")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await items.load_ctx(session, principal, "progress_report", report_id)
    report: ProgressReport = ctx.item  # type: ignore[assignment]
    return await apr.activity(session, ctx.scholar, report.report_year, report.period)
