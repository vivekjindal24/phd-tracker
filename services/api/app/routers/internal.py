"""Internal read endpoints the export service consumes — same JWT auth, admin-only
(exports are a research-office privilege, SECURITY.md §10). Kept under /internal so
the export surface stays structured, never scattered."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..db import get_db
from ..errors import ApiError
from ..models import Milestone, ProgressReport, Scholar, Supervisor
from ..rbac import get_or_403

router = APIRouter(prefix="/internal", tags=["internal"])


def _admin_only(actor: Actor) -> None:
	if actor.role != "admin":
		raise ApiError(403, "permission_denied", "Exports are restricted to the research office")


@router.get("/reports/{id}/export-view")
async def report_export_view(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> dict:
	_admin_only(actor)
	report = await get_or_403(db, ProgressReport, id, actor)
	scholar = await db.scalar(
		select(Scholar).where(Scholar.id == report.scholar_id, Scholar.deleted_at.is_(None))
	)
	supervisor = None
	if scholar is not None and scholar.supervisor_id is not None:
		supervisor = await db.get(Supervisor, scholar.supervisor_id)
	if scholar is None:
		raise ApiError(409, "conflict", "Report's scholar is missing")
	return {
		"report": {
			"id": str(report.id),
			"report_year": report.report_year,
			"period": report.period,
			"summary": report.summary,
			"supervisor_comment": report.supervisor_comment,
			"approved_on": str(report.approved_on) if report.approved_on else None,
			"state": report.state,
			"created_at": str(report.created_at),
		},
		"scholar": {
			"scholar_name": scholar.scholar_name,
			"roll_number": scholar.roll_number,
			"department": scholar.department,
			"admission_date": str(scholar.admission_date),
			"stage": scholar.stage,
		},
		"supervisor": {"full_name": supervisor.full_name} if supervisor else None,
	}


@router.get("/milestones")
async def milestones_export_view(
	scholar_id: UUID | None = None,
	department: str | None = None,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> list[dict]:
	_admin_only(actor)
	stmt = (
		select(Milestone, Scholar)
		.join(Scholar, Milestone.scholar_id == Scholar.id)
		.where(Milestone.deleted_at.is_(None), Scholar.deleted_at.is_(None))
	)
	if scholar_id is not None:
		stmt = stmt.where(Milestone.scholar_id == scholar_id)
	if department is not None:
		stmt = stmt.where(Scholar.department == department)
	rows = (await db.execute(stmt.order_by(Milestone.created_at.desc()))).all()
	return [
		{
			"scholar_name": scholar.scholar_name,
			"roll_number": scholar.roll_number,
			"department": scholar.department,
			"milestone_type": ms.milestone_type,
			"status": ms.status,
			"approval_body": ms.approval_body,
			"resolution_number": ms.resolution_number,
			"resolution_date": str(ms.resolution_date) if ms.resolution_date else None,
			"notes": ms.notes,
		}
		for ms, scholar in rows
	]