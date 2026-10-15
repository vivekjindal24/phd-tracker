"""Scholar directory — read scoped (own / own scholars / all), writes admin-only.
Scholar create/patch validates the UGC supervision cap (8/6/4 by designation).
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import insert, list_page, live_and_scoped, soft_delete, update
from ..db import get_db
from ..errors import ApiError
from ..models import Scholar, Supervisor, User
from ..rbac import get_or_403, require_perm
from ..schemas import Page, ScholarIn, ScholarOut, ScholarPatch

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
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> dict:
	require_perm(actor.role, "scholars", "read")
	return await list_page(db, live_and_scoped(Scholar, actor), page, per_page)


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