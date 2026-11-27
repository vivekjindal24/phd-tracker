"""Whether the audit trail is intact (SECURITY.md §6). Postgres seals each entry as it is
written and checks the whole chain (migration 0068); this asks it, and tells the root admins
when an entry no longer matches its seal."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OrgUnit, RoleAssignment
from app.notify import notify
from app.schemas import AuditIntegrity

log = logging.getLogger("anveshan.audit_trail")


async def check(session: AsyncSession) -> AuditIntegrity:
    # ponytail: reads every entry each time; check from the last good entry if it gets slow.
    row = (await session.execute(text("SELECT * FROM core.audit_check()"))).one()
    return AuditIntegrity(
        entries=row.entries,
        intact=row.broken_at is None,
        broken_at=row.broken_at,
        head=row.head,
        checked_at=datetime.now(UTC),
    )


async def _root_admins(session: AsyncSession) -> list[uuid.UUID]:
    root = select(OrgUnit.path).where(OrgUnit.parent_id.is_(None), OrgUnit.deleted_at.is_(None))
    rows = await session.scalars(
        select(RoleAssignment.user_id)
        .join(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
        .where(
            RoleAssignment.deleted_at.is_(None),
            RoleAssignment.role == "admin",
            OrgUnit.path == root.scalar_subquery(),
        )
    )
    return list(rows)


async def daily(session: AsyncSession) -> dict[str, object]:
    """The daily job's check: a broken chain is logged and put before the root admins."""
    result = await check(session)
    if not result.intact:
        log.error("audit trail broken at entry %s of the chain", result.broken_at)
        notify(
            session,
            await _root_admins(session),
            "system",
            "The audit trail has been tampered with",
            f"Audit entry {result.broken_at} no longer matches its seal: it, or the one before "
            "it, was changed or removed outside Anveshan. Keep a copy of the database as it is "
            "now and ask whoever runs the server to compare it with the nightly backups.",
            "/audit",
        )
    return {"audit_trail_intact": result.intact, "audit_entries": result.entries}
