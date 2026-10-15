"""Shared list/create/soft-delete plumbing — the part every entity router repeats.
Ownership always flows through rbac.scope; nothing here can bypass it.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit import snapshot, write_audit
from .models import Base
from .rbac import scope


def live_and_scoped(model: type, actor, extra: list[Any] | None = None) -> Select:
	stmt: Select = select(model).where(model.deleted_at.is_(None))
	condition = scope(model, actor)
	if condition is not None:
		stmt = stmt.where(condition)
	if extra:
		stmt = stmt.where(*extra)
	return stmt


async def list_page(db: AsyncSession, stmt: Select, page: int, per_page: int) -> dict:
	total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
	items = (
		await db.scalars(stmt.limit(per_page).offset((page - 1) * per_page))
	).all()
	return {"items": items, "total": total or 0, "page": page, "per_page": per_page}


async def insert(db: AsyncSession, obj: Base, actor, entity: str) -> Base:
	"""Add, flush (so unique violations surface as mapped 409s here), audit, commit."""
	db.add(obj)
	await db.flush()
	await write_audit(
		db,
		table_name=obj.__tablename__,
		record_id=obj.id,
		action="insert",
		actor_id=actor.user.id,
		actor_role=actor.role,
		data=snapshot(obj),
	)
	await db.commit()
	await db.refresh(obj)
	return obj


async def update(db: AsyncSession, obj: Base, actor, entity: str) -> Base:
	prev = snapshot(obj)
	await write_audit(
		db,
		table_name=obj.__tablename__,
		record_id=obj.id,
		action="update",
		actor_id=actor.user.id,
		actor_role=actor.role,
		prev=prev,
		data=snapshot(obj),
	)
	await db.commit()
	await db.refresh(obj)
	return obj


async def soft_delete(db: AsyncSession, obj: Base, actor) -> None:
	obj.deleted_at = datetime.now(UTC)
	await write_audit(
		db,
		table_name=obj.__tablename__,
		record_id=obj.id,
		action="soft_delete",
		actor_id=actor.user.id,
		actor_role=actor.role,
		prev=snapshot(obj),
	)
	await db.commit()