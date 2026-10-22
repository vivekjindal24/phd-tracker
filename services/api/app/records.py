"""Visibility of a polymorphic record (comments hang off these). One answer per table,
always reusing the record's own rules — never a second copy of them (SECURITY.md §3)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, meetings, scope
from app.auth.principal import Principal
from app.errors import forbidden
from app.models import Meeting, Milestone, OrgUnit, Scholar


async def require_read(
    session: AsyncSession, principal: Principal, table: str, record_id: uuid.UUID
) -> tuple[Scholar, str]:
    """403 unless the caller may read the record; returns its scholar and web link."""
    if table == "scholars":
        scholar = await scope.get_scholar_or_403(session, principal, record_id)
        return scholar, f"/scholars/{scholar.id}"
    if table == "progress_reports":
        ctx = await items.load_ctx(session, principal, "progress_report", record_id)
        return ctx.scholar, ctx.link
    if table == "meetings":
        row = (
            await session.execute(
                select(Meeting, Scholar, OrgUnit.path)
                .join(Scholar, Scholar.id == Meeting.scholar_id)
                .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
                .where(
                    Meeting.id == record_id,
                    Meeting.deleted_at.is_(None),
                    scope.scholar_predicate(principal, "meetings"),
                )
            )
        ).first()
        # Comments discuss the minutes: only viewers who may read the minutes see them.
        if row is None or not meetings.sees_full(principal, row[0], row[1], row[2]):
            raise forbidden()
        return row[1], f"/meetings/{record_id}"
    if table == "milestones":
        row = (
            await session.execute(
                select(Milestone, Scholar)
                .join(Scholar, Scholar.id == Milestone.scholar_id)
                .where(
                    Milestone.id == record_id,
                    Milestone.deleted_at.is_(None),
                    scope.scholar_predicate(principal, "milestones"),
                )
            )
        ).first()
        if row is None:
            raise forbidden()
        return row[1], f"/scholars/{row[1].id}"
    raise forbidden()
