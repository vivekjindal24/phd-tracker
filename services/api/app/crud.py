"""Shared write helpers. Every mutation writes exactly one audit_log row (AGENTS.md §3)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.models import AuditLog
from app.models.base import Base

REDACTED_COLUMNS = frozenset({"password_hash", "token_hash"})


def _json(value: Any) -> Any:
    if isinstance(value, uuid.UUID | date | datetime | Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json(v) for v in value]
    return value


def snapshot(obj: Base) -> dict[str, Any]:
    """Column values for the audit trail, hashes redacted, bytes never included."""
    out: dict[str, Any] = {}
    for column in inspect(obj).mapper.column_attrs:
        if column.key in REDACTED_COLUMNS:
            out[column.key] = "[redacted]"
            continue
        value = getattr(obj, column.key)
        if not isinstance(value, bytes | memoryview):
            out[column.key] = _json(value)
    return out


def _record_id(obj: Base) -> str:
    return ",".join(str(v) for v in inspect(obj).identity or ())


def audit(
    session: AsyncSession,
    principal: Principal | None,
    obj: Base,
    action: str,
    prev: dict[str, Any] | None = None,
    from_state: str | None = None,
    to_state: str | None = None,
) -> None:
    session.add(
        AuditLog(
            table_name=obj.__tablename__,
            record_id=_record_id(obj),
            action=action,
            from_state=from_state,
            to_state=to_state,
            prev=prev,
            data=snapshot(obj),
            actor_id=principal.user_id if principal else None,
            actor_roles=sorted(principal.roles) if principal else [],
        )
    )


async def insert[M: Base](session: AsyncSession, principal: Principal | None, obj: M) -> M:
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    audit(session, principal, obj, "insert")
    return obj


async def update[M: Base](
    session: AsyncSession, principal: Principal, obj: M, changes: dict[str, Any]
) -> M:
    if not changes:
        return obj
    prev = snapshot(obj)
    for key, value in changes.items():
        setattr(obj, key, value)
    await session.flush()
    await session.refresh(obj)
    audit(session, principal, obj, "update", prev=prev)
    return obj


async def soft_delete[M: Base](session: AsyncSession, principal: Principal, obj: M) -> M:
    prev = snapshot(obj)
    obj.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
    await session.flush()
    await session.refresh(obj)  # server-side updated_at is expired by the flush
    audit(session, principal, obj, "soft_delete", prev=prev)
    return obj
