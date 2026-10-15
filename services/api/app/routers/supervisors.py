"""Supervisor directory — read for every role; writes are admin-only."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import Actor, get_actor
from ..crud import insert, list_page, live_and_scoped, soft_delete, update
from ..db import get_db
from ..models import Supervisor
from ..rbac import get_or_403, require_perm
from ..schemas import Page, SupervisorIn, SupervisorOut, SupervisorPatch

router = APIRouter(prefix="/supervisors", tags=["supervisors"])


@router.get("", response_model=Page[SupervisorOut])
async def list_supervisors(
	page: int = Query(default=1, ge=1),
	per_page: int = Query(default=20, ge=1, le=100),
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> dict:
	require_perm(actor.role, "supervisors", "read")
	return await list_page(db, live_and_scoped(Supervisor, actor), page, per_page)


@router.get("/{id}", response_model=SupervisorOut)
async def get_supervisor(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> Supervisor:
	require_perm(actor.role, "supervisors", "read")
	return await get_or_403(db, Supervisor, id, actor)


@router.post("", response_model=SupervisorOut, status_code=201)
async def create_supervisor(
	body: SupervisorIn,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> Supervisor:
	require_perm(actor.role, "supervisors", "create")
	return await insert(db, Supervisor(**body.model_dump()), actor, "supervisors")


@router.patch("/{id}", response_model=SupervisorOut)
async def patch_supervisor(
	id: UUID,
	body: SupervisorPatch,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> Supervisor:
	require_perm(actor.role, "supervisors", "write")
	sup = await get_or_403(db, Supervisor, id, actor)
	for key, value in body.model_dump(exclude_unset=True).items():
		setattr(sup, key, value)
	return await update(db, sup, actor, "supervisors")


@router.delete("/{id}", status_code=204)
async def delete_supervisor(
	id: UUID, actor: Actor = Depends(get_actor), db: AsyncSession = Depends(get_db)
) -> None:
	require_perm(actor.role, "supervisors", "delete")
	sup = await get_or_403(db, Supervisor, id, actor)
	await soft_delete(db, sup, actor)