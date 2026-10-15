"""Role matrix (data, not code paths) + row-level ownership scoping.

The v1 Frappe gap — a scholar could read every other scholar's records — is closed
by construction here: every list/get goes through scope()/get_or_403(), so no
router can skip the ownership filter.
"""

import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import ApiError
from .models import Meeting, Milestone, ProgressReport, Scholar

# role → entity → allowed actions. `delete` means soft delete; `write` means update.
MATRIX: dict[str, dict[str, set[str]]] = {
	"scholar": {
		"scholars": {"read"},  # own row only — scope()
		"supervisors": {"read"},  # directory: all rows
		"meetings": {"create", "read", "write"},
		"reports": {"create", "read", "write", "submit", "resubmit"},
		"milestones": {"read"},
	},
	"supervisor": {
		"scholars": {"read"},  # own scholars only — scope()
		"supervisors": {"read"},  # directory: all rows
		"meetings": {"create", "read", "write"},
		"reports": {"read", "write", "approve", "send_back"},
		"milestones": {"create", "read", "write"},
	},
	"admin": {
		"scholars": {"create", "read", "write", "delete"},
		"supervisors": {"create", "read", "write", "delete"},
		"meetings": {"create", "read", "write", "delete"},
		"reports": {"create", "read", "write", "delete", "submit", "approve", "send_back", "resubmit"},
		"milestones": {"create", "read", "write", "delete"},
	},
}


def can(role: str, entity: str, action: str) -> bool:
	return action in MATRIX.get(role, {}).get(entity, set())


def require_perm(role: str, entity: str, action: str) -> None:
	if not can(role, entity, action):
		raise ApiError(403, "permission_denied", f"Role '{role}' may not {action} {entity}")


# --- ownership scoping -------------------------------------------------------

def scope(model: type, actor) -> Any:
	"""WHERE fragment limiting `model` to rows this actor may see; None = unrestricted.

	Meeting/Report/Milestone rows hang off scholar_id, so "own / own scholars" is the
	single ownership rule for all of them plus Scholar itself.
	"""
	if actor.role == "admin":
		return None
	if model is Scholar:
		if actor.role == "scholar":
			return Scholar.id == actor.scholar_id
		return Scholar.supervisor_id == actor.supervisor_id
	if model in (Meeting, ProgressReport, Milestone):
		if actor.role == "scholar":
			return model.scholar_id == actor.scholar_id
		own: Select = select(Scholar.id).where(
			Scholar.supervisor_id == actor.supervisor_id, Scholar.deleted_at.is_(None)
		)
		return model.scholar_id.in_(own.scalar_subquery())
	return None  # Supervisor directory: readable by all roles


async def get_or_403(db: AsyncSession, model: type, record_id: uuid.UUID, actor) -> Any:
	"""Fetch one live row the actor may see; 403 (not 404) when invisible — existence is not leaked."""
	stmt = select(model).where(model.id == record_id, model.deleted_at.is_(None))
	condition = scope(model, actor)
	if condition is not None:
		stmt = stmt.where(condition)
	obj = await db.scalar(stmt)
	if obj is None:
		raise ApiError(403, "permission_denied", "Record not found")
	return obj


async def ensure_scholar_visible(db: AsyncSession, actor, scholar_id: uuid.UUID) -> None:
	"""Write-path ownership guard: a scholar acts on their own record, a supervisor on their own scholars."""
	if actor.role == "admin":
		return
	scholar = await get_or_403(db, Scholar, scholar_id, actor)
	if actor.role == "scholar" and scholar.id != actor.scholar_id:
		raise ApiError(403, "permission_denied", "You can only act on your own records")