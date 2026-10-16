"""Milestones — recorded by the research office or the scholar's supervisor; read-only to the scholar."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import apply_list_opts, insert, list_page, live_and_scoped, soft_delete, update
from ..db import get_db
from ..models import Milestone
from ..rbac import ensure_scholar_visible, get_or_403, require_perm
from ..schemas import MilestoneIn, MilestoneOut, MilestonePatch, MilestoneStatus, MilestoneType, Page

router = APIRouter(prefix="/milestones", tags=["milestones"])


@router.get("", response_model=Page[MilestoneOut])
async def list_milestones(
	page: int = Query(default=1, ge=1),
	per_page: int = Query(default=20, ge=1, le=100),
	sort: str | None = None,
	scholar_id: UUID | None = None,
	status: MilestoneStatus | None = None,
	milestone_type: MilestoneType | None = None,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> dict:
	require_perm(actor.role, "milestones", "read")
	stmt = apply_list_opts(
		Milestone,
		live_and_scoped(Milestone, actor),
		sort,
		{"scholar_id": scholar_id, "status": status, "milestone_type": milestone_type},
	)
	return await list_page(db, stmt, page, per_page)


@router.get("/{id}", response_model=MilestoneOut)
async def get_milestone(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Milestone:
	require_perm(actor.role, "milestones", "read")
	return await get_or_403(db, Milestone, id, actor)


@router.post("", response_model=MilestoneOut, status_code=201)
async def create_milestone(
	body: MilestoneIn, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Milestone:
	require_perm(actor.role, "milestones", "create")
	await ensure_scholar_visible(db, actor, body.scholar_id)
	return await insert(db, Milestone(**body.model_dump()), actor, "milestones")


@router.patch("/{id}", response_model=MilestoneOut)
async def patch_milestone(
	id: UUID,
	body: MilestonePatch,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> Milestone:
	require_perm(actor.role, "milestones", "write")
	milestone = await get_or_403(db, Milestone, id, actor)
	for key, value in body.model_dump(exclude_unset=True).items():
		setattr(milestone, key, value)
	return await update(db, milestone, actor, "milestones")


@router.delete("/{id}", status_code=204)
async def delete_milestone(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> None:
	require_perm(actor.role, "milestones", "delete")
	milestone = await get_or_403(db, Milestone, id, actor)
	await soft_delete(db, milestone, actor)