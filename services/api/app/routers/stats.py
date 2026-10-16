"""Dashboard aggregates — one endpoint, every role, scoped by live_and_scoped.

A scholar's dashboard is their slice of the data with zero role branching. Recent
activity (raw audit rows) is admin-only: scoping polymorphic audit entries to
other roles needs per-table joins and snapshot redaction.

ponytail: no caching — pilot volume; add if the dashboard ever shows on a profile.
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import live_and_scoped
from ..db import get_db
from ..models import AuditLog, Meeting, ProgressReport, Scholar, Supervisor
from ..rbac import scope
from ..schemas import ActivityOut, DashboardOut, UpcomingMeetingOut

router = APIRouter(prefix="/stats", tags=["stats"])


async def _count(db: AsyncSession, stmt) -> int:
	return await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))


async def _group(db: AsyncSession, model: type, key: str, actor: Actor) -> dict[str, int]:
	"""count-per-value over the actor's scoped rows (e.g. reports by state, scholars by stage)."""
	column = getattr(model, key)
	stmt = select(column, func.count()).where(model.deleted_at.is_(None))
	condition = scope(model, actor)
	if condition is not None:
		stmt = stmt.where(condition)
	rows = await db.execute(stmt.group_by(column))
	return dict(rows.all())


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)) -> DashboardOut:
	reports_by_state = await _group(db, ProgressReport, "state", actor)
	scholars_by_stage = await _group(db, Scholar, "stage", actor)

	rows = await db.execute(
		live_and_scoped(Meeting, actor)
		.where(Meeting.meeting_date >= date.today())
		.join(Scholar, Meeting.scholar_id == Scholar.id)
		.add_columns(Scholar.scholar_name)
		.order_by(Meeting.meeting_date)
		.limit(5)
	)
	upcoming = [
		UpcomingMeetingOut(
			id=meeting.id,
			scholar_id=meeting.scholar_id,
			scholar_name=name,
			meeting_date=meeting.meeting_date,
			agenda=meeting.agenda,
		)
		for meeting, name in rows
	]

	recent_activity: list[ActivityOut] = []
	if actor.role == "admin":
		audit_rows = await db.scalars(select(AuditLog).order_by(AuditLog.at.desc()).limit(10))
		recent_activity = [
			ActivityOut(
				id=row.id,
				at=row.at,
				table_name=row.table_name,
				action=row.action,
				actor_role=row.actor_role,
			)
			for row in audit_rows
		]

	return DashboardOut(
		scholars=await _count(db, live_and_scoped(Scholar, actor)),
		supervisors=await _count(db, live_and_scoped(Supervisor, actor)),
		reports_by_state=reports_by_state,
		scholars_by_stage=scholars_by_stage,
		upcoming_meetings=upcoming,
		recent_activity=recent_activity,
	)