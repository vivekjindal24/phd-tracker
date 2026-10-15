"""Global search — ILIKE partial match over the core text fields (DATABASE.md §6),
grouped by entity, scoped by the same ownership filter as every other read."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import live_and_scoped
from ..db import get_db
from ..models import Meeting, Milestone, ProgressReport, Scholar, Supervisor
from ..schemas import SearchOut

router = APIRouter(prefix="/search", tags=["search"])

SEARCH_LIMIT = 20


@router.get("", response_model=SearchOut)
async def search(
	q: str = Query(min_length=1),
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> dict:
	like = f"%{q}%"

	async def run(model, columns) -> list:
		stmt = live_and_scoped(model, actor, [or_(*[col.ilike(like) for col in columns])])
		return list((await db.scalars(stmt.limit(SEARCH_LIMIT))).all())

	return {
		"scholars": await run(Scholar, [Scholar.scholar_name, Scholar.roll_number]),
		"supervisors": await run(Supervisor, [Supervisor.full_name]),
		"meetings": await run(Meeting, [Meeting.agenda]),
		"reports": await run(ProgressReport, [ProgressReport.summary]),
		"milestones": await run(Milestone, [Milestone.milestone_type, Milestone.resolution_number]),
	}