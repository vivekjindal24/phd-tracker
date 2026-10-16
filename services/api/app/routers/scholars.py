"""Scholar directory — read scoped (own / own scholars / all), writes admin-only.
Scholar create/patch validates the UGC supervision cap (8/6/4 by designation).
"""

import uuid
from datetime import UTC, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import apply_list_opts, insert, list_page, live_and_scoped, soft_delete, update
from ..db import get_db
from ..errors import ApiError
from ..models import AuditLog, Comment, Meeting, Milestone, ProgressReport, Scholar, Supervisor, User
from ..rbac import get_or_403, require_perm
from ..schemas import (
	MeetingOut,
	MilestoneOut,
	Page,
	ReportOut,
	ScholarIn,
	ScholarOut,
	ScholarPatch,
	Stage,
	TimelineEvent,
	TimelineOut,
)

router = APIRouter(prefix="/scholars", tags=["scholars"])

# UGC 2022 supervision caps by designation; max_scholars can only tighten them.
DESIGNATION_CAPS = {"Professor": 8, "Associate Professor": 6, "Assistant Professor": 4}


async def check_supervisor_cap(
	db: AsyncSession, supervisor_id: uuid.UUID, exclude_scholar_id: uuid.UUID | None = None
) -> None:
	sup = await db.get(Supervisor, supervisor_id)
	if sup is None or sup.deleted_at is not None:
		raise ApiError(422, "unknown_supervisor", "Supervisor does not exist")
	cap = min(sup.max_scholars, DESIGNATION_CAPS[sup.designation])
	stmt = select(Scholar).where(
		Scholar.supervisor_id == supervisor_id, Scholar.deleted_at.is_(None)
	)
	if exclude_scholar_id is not None:
		stmt = stmt.where(Scholar.id != exclude_scholar_id)
	count = await db.scalar(select(func.count()).select_from(stmt.subquery()))
	# ponytail: count-then-insert race; advisory lock if concurrent admins ever matter
	if count is not None and count >= cap:
		raise ApiError(
			409,
			"supervisor_cap_exceeded",
			f"{sup.full_name} already supervises the UGC cap of {cap} scholars",
		)


async def validate_user_link(db: AsyncSession, user_id: uuid.UUID) -> None:
	user = await db.get(User, user_id)
	if user is None or user.deleted_at is not None or user.role != "scholar":
		raise ApiError(422, "invalid_user_link", "user_id must be an existing scholar user")


@router.get("", response_model=Page[ScholarOut])
async def list_scholars(
	page: int = Query(default=1, ge=1),
	per_page: int = Query(default=20, ge=1, le=100),
	sort: str | None = None,
	stage: Stage | None = None,
	department: str | None = None,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> dict:
	require_perm(actor.role, "scholars", "read")
	stmt = apply_list_opts(
		Scholar, live_and_scoped(Scholar, actor), sort, {"stage": stage, "department": department}
	)
	return await list_page(db, stmt, page, per_page)


@router.get("/{id}/timeline", response_model=TimelineOut)
async def scholar_timeline(
	id: uuid.UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> TimelineOut:
	"""Merged per-scholar event feed — five boring selects, one Python merge.

	ponytail: no pagination; fetch-window the queries when a scholar's history grows past a screen.
	"""
	require_perm(actor.role, "scholars", "read")
	scholar = await get_or_403(db, Scholar, id, actor)

	meetings = (
		await db.scalars(
			live_and_scoped(Meeting, actor).where(Meeting.scholar_id == scholar.id)
		)
	).all()
	reports = (
		await db.scalars(
			live_and_scoped(ProgressReport, actor).where(ProgressReport.scholar_id == scholar.id)
		)
	).all()
	report_ids = [r.id for r in reports]
	transitions = (
		await db.scalars(
			select(AuditLog).where(
				AuditLog.table_name == "progress_reports",
				AuditLog.record_id.in_(report_ids or [uuid.uuid4()]),
				AuditLog.action == "transition",
			)
		)
	).all()
	milestones = (
		await db.scalars(live_and_scoped(Milestone, actor).where(Milestone.scholar_id == scholar.id))
	).all()
	pairs = [("scholars", scholar.id)] + [
		("meetings", m.id) for m in meetings
	] + [("progress_reports", r.id) for r in reports] + [("milestones", m.id) for m in milestones]
	comments = (
		await db.scalars(
			select(Comment).where(
				tuple_(Comment.table_name, Comment.record_id).in_(pairs),
				Comment.deleted_at.is_(None),
			)
		)
	).all()

	events = [
		TimelineEvent(
			kind="meeting",
			at=datetime.combine(m.meeting_date, time.min, tzinfo=UTC),
			data=MeetingOut.model_validate(m).model_dump(mode="json"),
		)
		for m in meetings
	] + [
		TimelineEvent(
			kind="report",
			at=r.created_at,
			data=ReportOut.model_validate(r).model_dump(mode="json"),
		)
		for r in reports
	] + [
		TimelineEvent(
			kind="transition",
			at=t.at,
			data={
				"report_id": str(t.record_id),
				"from_state": t.from_state,
				"to_state": t.to_state,
			},
		)
		for t in transitions
	] + [
		TimelineEvent(
			kind="milestone",
			at=datetime.combine(m.resolution_date, time.min, tzinfo=UTC)
			if m.resolution_date
			else m.created_at,
			data=MilestoneOut.model_validate(m).model_dump(mode="json"),
		)
		for m in milestones
	] + [
		TimelineEvent(
			kind="comment",
			at=c.created_at,
			data={"author_id": str(c.author_id), "body": c.body, "table_name": c.table_name},
		)
		for c in comments
	]
	events.sort(key=lambda e: e.at, reverse=True)
	return TimelineOut(scholar_id=scholar.id, events=events)


@router.get("/{id}", response_model=ScholarOut)
async def get_scholar(
	id: uuid.UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Scholar:
	require_perm(actor.role, "scholars", "read")
	return await get_or_403(db, Scholar, id, actor)


@router.post("", response_model=ScholarOut, status_code=201)
async def create_scholar(
	body: ScholarIn, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Scholar:
	require_perm(actor.role, "scholars", "create")
	if body.supervisor_id is not None:
		await check_supervisor_cap(db, body.supervisor_id)
	if body.user_id is not None:
		await validate_user_link(db, body.user_id)
	return await insert(db, Scholar(**body.model_dump()), actor, "scholars")


@router.patch("/{id}", response_model=ScholarOut)
async def patch_scholar(
	id: uuid.UUID,
	body: ScholarPatch,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> Scholar:
	require_perm(actor.role, "scholars", "write")
	scholar = await get_or_403(db, Scholar, id, actor)
	patch: dict[str, Any] = body.model_dump(exclude_unset=True)
	if "supervisor_id" in patch and patch["supervisor_id"] != scholar.supervisor_id:
		if patch["supervisor_id"] is not None:
			await check_supervisor_cap(db, patch["supervisor_id"], exclude_scholar_id=scholar.id)
	if "user_id" in patch and patch["user_id"] is not None:
		await validate_user_link(db, patch["user_id"])
	for key, value in patch.items():
		setattr(scholar, key, value)
	return await update(db, scholar, actor, "scholars")


@router.delete("/{id}", status_code=204)
async def delete_scholar(
	id: uuid.UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> None:
	require_perm(actor.role, "scholars", "delete")
	scholar = await get_or_403(db, Scholar, id, actor)
	await soft_delete(db, scholar, actor)