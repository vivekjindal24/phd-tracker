"""Reading the audit log (SECURITY.md §3). Rows are written by crud.py and workflow.py; this
only answers who did what to which record and when. Recorded values never leave: a snapshot
may hold meeting minutes, examiner names or amounts its reader has no right to."""

import uuid
from datetime import date, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope
from app.auth.principal import Principal
from app.db import get_session
from app.enums import AuditAction
from app.models import AuditLog, Scholar, User
from app.rbac import require_perm
from app.schemas import AuditRow
from app.sorting import Sort, ordered

router = APIRouter(tags=["audit"])
# Drafts and their versions are the scholar's and supervisor's alone (PRD M3): not even that
# one exists is shown here.
HIDDEN_TABLES = ("documents", "document_versions")
SCHOLAR_ID = AuditLog.data["scholar_id"].astext
BOOKKEEPING = ("updated_at", "updated_by")


def _state(state: str | None, snapshot: dict[str, Any] | None) -> str | None:
    """A chain item's state with its step, so a move between steps does not read as no move."""
    step = (snapshot or {}).get("current_step")
    return f"{state}, step {step + 1}" if state and step is not None else state


def _about(scholar_ids) -> Any:
    """Rows about these scholars: the scholar's own row, or any record carrying scholar_id."""
    text_ids = select(cast(scholar_ids.c.id, String))
    return or_(
        (AuditLog.table_name == "scholars") & AuditLog.record_id.in_(text_ids),
        SCHOLAR_ID.in_(text_ids),
    )


def _changed(row: AuditLog) -> list[str]:
    """Names of the columns an update changed; bookkeeping columns left out."""
    if row.action != "update" or not row.prev or not row.data:
        return []
    return sorted(
        k for k, v in row.data.items() if k not in BOOKKEEPING and row.prev.get(k, v) != v
    )


@router.get("/audit-log", response_model=list[AuditRow])
async def read_audit_log(
    table_name: str | None = Query(default=None, max_length=60),
    action: AuditAction | None = None,
    actor_id: uuid.UUID | None = None,
    scholar_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Sort = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_perm("audit_log", "read")),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_id)
    stmt = stmt.where(AuditLog.table_name.not_in(HIDDEN_TABLES))
    if not (principal.is_root_admin or principal.reads_all):
        # A scoped admin: only what concerns scholars of their subtree. Records with no scholar
        # (people, units, settings) stay with those who read the whole university.
        paths = principal.unit_paths("admin")
        mine = select(Scholar.id).where(Scholar.unit_id.in_(scope.subtree_unit_ids(paths)))
        stmt = stmt.where(_about(mine.subquery()))
    if scholar_id:
        one = select(Scholar.id).where(Scholar.id == scholar_id)
        stmt = stmt.where(_about(one.subquery()))
    if table_name:
        stmt = stmt.where(AuditLog.table_name == table_name)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if date_from:
        stmt = stmt.where(AuditLog.at >= datetime.combine(date_from, time.min).astimezone())
    if date_to:
        stmt = stmt.where(AuditLog.at <= datetime.combine(date_to, time.max).astimezone())
    # ponytail: filters on `at` and the jsonb scholar_id scan without an index of their own;
    # add (at) and an expression index on data->>'scholar_id' when the log grows large.
    columns = {
        "when": AuditLog.at,
        "who": User.full_name,
        "what": AuditLog.action,
        "record": AuditLog.table_name,
    }
    stmt = ordered(stmt, sort, columns, [AuditLog.at.desc()], AuditLog.id.desc())
    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    ids = {
        r.record_id if r.table_name == "scholars" else (r.data or {}).get("scholar_id")
        for r, _ in rows
    } - {None}
    names = dict(
        (
            await session.execute(
                select(cast(Scholar.id, String), User.full_name)
                .join(User, User.id == Scholar.user_id)
                .where(cast(Scholar.id, String).in_(ids))
            )
        ).all()
    )
    out = []
    for row, actor in rows:
        sid = row.record_id if row.table_name == "scholars" else (row.data or {}).get("scholar_id")
        out.append(
            {
                "id": row.id,
                "at": row.at,
                "actor": actor,
                "actor_roles": row.actor_roles,
                "action": row.action,
                "table_name": row.table_name,
                "record_id": row.record_id,
                "from_state": _state(row.from_state, row.prev),
                "to_state": _state(row.to_state, row.data),
                "fields": _changed(row),
                "scholar": {"id": sid, "name": names[sid]} if sid in names else None,
            }
        )
    return out
