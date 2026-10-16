"""Explicit audit writer — called after every mutation, no ORM event magic.
One row per change with full prev/new snapshots; workflow transitions add from/to state.
"""

from typing import Any

from sqlalchemy import LargeBinary
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditLog, Base


def snapshot(obj: Base) -> dict[str, Any]:
	"""Column values, JSON-safe (datetime/date/uuid → str; plain scalars pass through).
	bytea payloads (attachment content) are skipped — megabytes in an audit row buys nothing."""
	out: dict[str, Any] = {}
	for col in type(obj).__table__.columns:
		if isinstance(col.type, LargeBinary):
			continue
		val = getattr(obj, col.name)
		out[col.name] = val if val is None or isinstance(val, (int, float, str, bool)) else str(val)
	return out


async def write_audit(
	db: AsyncSession,
	*,
	table_name: str,
	record_id: Any,
	action: str,
	actor_id: Any,
	actor_role: str,
	from_state: str | None = None,
	to_state: str | None = None,
	prev: dict | None = None,
	data: dict | None = None,
) -> None:
	db.add(
		AuditLog(
			table_name=table_name,
			record_id=record_id,
			action=action,
			actor_id=actor_id,
			actor_role=actor_role,
			from_state=from_state,
			to_state=to_state,
			prev=prev,
			data=data,
		)
	)