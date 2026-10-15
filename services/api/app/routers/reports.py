"""Progress reports (APRs) — CRUD + the four workflow actions.

Edit rules follow UX_FLOWS: the owning scholar edits a draft/rejected report; the
supervisor comments on a submitted one; an approved report is immutable for everyone
(it is the compliance record).
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import insert, list_page, live_and_scoped, soft_delete, update
from ..db import get_db
from ..errors import ApiError
from ..models import ProgressReport
from ..rbac import ensure_scholar_visible, get_or_403, require_perm
from ..schemas import Page, ReportIn, ReportOut, ReportPatch
from ..workflow import apply_action

router = APIRouter(prefix="/reports", tags=["reports"])


async def _ensure_editable(report: ProgressReport, actor: Actor, patch: dict[str, Any]) -> None:
	if report.state == "approved":
		raise ApiError(422, "workflow_violation", "An approved report is immutable")
	if actor.role == "scholar" and report.state not in ("draft", "rejected"):
		raise ApiError(422, "workflow_violation", f"Cannot edit a report in state '{report.state}'")
	if actor.role == "scholar" and "supervisor_comment" in patch:
		raise ApiError(403, "permission_denied", "Only the supervisor may comment")
	if actor.role == "supervisor" and report.state != "submitted":
		raise ApiError(422, "workflow_violation", "You can only edit a submitted report")


@router.get("", response_model=Page[ReportOut])
async def list_reports(
	page: int = Query(default=1, ge=1),
	per_page: int = Query(default=20, ge=1, le=100),
	state: str | None = None,
	scholar_id: UUID | None = None,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> dict:
	require_perm(actor.role, "reports", "read")
	extra = []
	if state is not None:
		extra.append(ProgressReport.state == state)
	if scholar_id is not None:
		extra.append(ProgressReport.scholar_id == scholar_id)
	return await list_page(db, live_and_scoped(ProgressReport, actor, extra), page, per_page)


@router.get("/{id}", response_model=ReportOut)
async def get_report(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> ProgressReport:
	require_perm(actor.role, "reports", "read")
	return await get_or_403(db, ProgressReport, id, actor)


@router.post("", response_model=ReportOut, status_code=201)
async def create_report(
	body: ReportIn, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> ProgressReport:
	require_perm(actor.role, "reports", "create")
	await ensure_scholar_visible(db, actor, body.scholar_id)
	report = ProgressReport(**body.model_dump(), state="draft")
	return await insert(db, report, actor, "reports")


@router.patch("/{id}", response_model=ReportOut)
async def patch_report(
	id: UUID,
	body: ReportPatch,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> ProgressReport:
	require_perm(actor.role, "reports", "write")
	report = await get_or_403(db, ProgressReport, id, actor)
	patch = body.model_dump(exclude_unset=True)
	await _ensure_editable(report, actor, patch)
	for key, value in patch.items():
		setattr(report, key, value)
	return await update(db, report, actor, "reports")


@router.post("/{id}/{action}", response_model=ReportOut)
async def workflow_action(
	id: UUID,
	action: str,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> ProgressReport:
	if action not in {"submit", "approve", "send_back", "resubmit"}:
		raise ApiError(404, "not_found", "Unknown action")
	report = await get_or_403(db, ProgressReport, id, actor)
	await ensure_scholar_visible(db, actor, report.scholar_id)
	report = await apply_action(db, report, action, actor)
	await db.commit()
	await db.refresh(report)  # server-side onupdate must be reloaded before serialization
	return report


@router.delete("/{id}", status_code=204)
async def delete_report(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> None:
	require_perm(actor.role, "reports", "delete")
	report = await get_or_403(db, ProgressReport, id, actor)
	await soft_delete(db, report, actor)