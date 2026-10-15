"""Meeting records — created by the parties (scholar, their supervisor) or admin;
visible to both parties and the research office. Soft delete is admin-only."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import insert, list_page, live_and_scoped, soft_delete, update
from ..db import get_db
from ..errors import ApiError
from ..models import Meeting, Scholar, Supervisor
from ..rbac import ensure_scholar_visible, get_or_403, require_perm
from ..schemas import MeetingIn, MeetingOut, MeetingPatch, Page

router = APIRouter(prefix="/meetings", tags=["meetings"])


async def _validate_pair(db: AsyncSession, actor: Actor, scholar_id: UUID, supervisor_id: UUID) -> None:
	"""Ownership at the boundary: a scholar logs own meetings, a supervisor their own scholars'."""
	await ensure_scholar_visible(db, actor, scholar_id)
	if actor.role == "supervisor" and supervisor_id != actor.supervisor_id:
		raise ApiError(403, "permission_denied", "You can only log your own meetings")
	supervisor = await db.get(Supervisor, supervisor_id)
	scholar = await db.scalar(
		select(Scholar.id).where(Scholar.id == scholar_id, Scholar.deleted_at.is_(None))
	)
	if supervisor is None or supervisor.deleted_at is not None or scholar is None:
		raise ApiError(422, "unknown_party", "Scholar or supervisor does not exist")


@router.get("", response_model=Page[MeetingOut])
async def list_meetings(
	page: int = Query(default=1, ge=1),
	per_page: int = Query(default=20, ge=1, le=100),
	scholar_id: UUID | None = None,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> dict:
	require_perm(actor.role, "meetings", "read")
	extra = []
	if scholar_id is not None:
		extra.append(Meeting.scholar_id == scholar_id)
	return await list_page(db, live_and_scoped(Meeting, actor, extra), page, per_page)


@router.get("/{id}", response_model=MeetingOut)
async def get_meeting(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Meeting:
	require_perm(actor.role, "meetings", "read")
	return await get_or_403(db, Meeting, id, actor)


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(
	body: MeetingIn, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Meeting:
	require_perm(actor.role, "meetings", "create")
	await _validate_pair(db, actor, body.scholar_id, body.supervisor_id)
	return await insert(db, Meeting(**body.model_dump()), actor, "meetings")


@router.patch("/{id}", response_model=MeetingOut)
async def patch_meeting(
	id: UUID,
	body: MeetingPatch,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> Meeting:
	require_perm(actor.role, "meetings", "write")
	meeting = await get_or_403(db, Meeting, id, actor)
	for key, value in body.model_dump(exclude_unset=True).items():
		setattr(meeting, key, value)
	return await update(db, meeting, actor, "meetings")


@router.delete("/{id}", status_code=204)
async def delete_meeting(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> None:
	require_perm(actor.role, "meetings", "delete")
	meeting = await get_or_403(db, Meeting, id, actor)
	await soft_delete(db, meeting, actor)