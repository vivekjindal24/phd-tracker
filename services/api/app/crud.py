"""Shared list/create/soft-delete plumbing — the part every entity router repeats.
Ownership always flows through rbac.scope; nothing here can bypass it.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit import snapshot, write_audit
from .errors import ApiError
from .models import Base, Meeting, Milestone, ProgressReport, Scholar, Supervisor
from .rbac import scope

# Sortable columns per model — the whitelist that makes the `sort` query param safe.
SORTABLE: dict[type, set[str]] = {
	Scholar: {"scholar_name", "roll_number", "department", "admission_date", "stage", "created_at"},
	Supervisor: {"full_name", "department", "designation", "created_at"},
	Meeting: {"meeting_date", "created_at"},
	ProgressReport: {"report_year", "state", "created_at"},
	Milestone: {"milestone_type", "status", "resolution_date", "created_at"},
}


def apply_list_opts(model: type, stmt: Select, sort: str | None, filters: dict[str, Any]) -> Select:
	"""Whitelisted order_by + equality WHEREs, composed AFTER live_and_scoped so
	sorting/filtering can never widen the RBAC scope.

	ponytail: equality-only filters and single-field sort; add operators when a
	screen needs them.
	"""
	if sort:
		desc, col = sort.startswith("-"), sort.lstrip("+-")
		if col not in SORTABLE.get(model, set()):
			raise ApiError(422, "bad_sort", f"Cannot sort '{model.__tablename__}' by '{col}'")
		stmt = stmt.order_by(getattr(model, col).desc() if desc else getattr(model, col))
	else:
		stmt = stmt.order_by(model.created_at.desc())  # stable pages: unsorted ≠ random order
	for key, value in filters.items():
		if value is not None:
			stmt = stmt.where(getattr(model, key) == value)
	return stmt


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