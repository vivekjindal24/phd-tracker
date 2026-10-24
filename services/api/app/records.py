"""Access to a polymorphic record — comments and files hang off these. One answer per table,
always reusing the record's own rules — never a second copy of them (SECURITY.md §3)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, meetings, scope, thesis, workflow
from app.auth.principal import Principal
from app.errors import ApiError, forbidden
from app.models import (
    Conference,
    Document,
    Meeting,
    Milestone,
    OrgUnit,
    Scholar,
    ShodhgangaDeposit,
    Viva,
)
from app.modules import module_enabled
from app.rbac import can


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
    if table == "publications":
        ctx = await items.load_ctx(session, principal, "publication", record_id)
        return ctx.scholar, ctx.link
    if table == "conferences":
        _, scholar = await _conference(session, principal, record_id)
        return scholar, f"/scholars/{scholar.id}"
    if table == "documents":
        doc, scholar = await document_or_403(session, principal, record_id)
        return scholar, f"/documents/{doc.id}"
    if table == "thesis_submissions":
        ctx = await thesis.load_thesis(session, principal, record_id)
        return ctx.scholar, ctx.link
    if table == "coursework_clearances":
        ctx = await items.load_ctx(session, principal, "coursework_clearance", record_id)
        return ctx.scholar, ctx.link
    if table == "examiner_reports":
        _, ctx = await thesis.report_ctx(session, principal, record_id)
        return ctx.scholar, ctx.link
    if table in THESIS_CHILDREN:
        _, ctx = await thesis.child_ctx(session, principal, THESIS_CHILDREN[table], record_id)
        return ctx.scholar, ctx.link
    raise forbidden()


THESIS_CHILDREN: dict[str, type] = {"vivas": Viva, "shodhganga_deposits": ShodhgangaDeposit}


async def document_or_403(
    session: AsyncSession, principal: Principal, record_id: uuid.UUID
) -> tuple[Document, Scholar]:
    """A draft/chapter: the scholar and their supervisor(s) only (PRD M3)."""
    if not await module_enabled(session, "documents"):
        raise ApiError(404, "module_disabled", "This feature is not enabled.")
    row = (
        await session.execute(
            select(Document, Scholar)
            .join(Scholar, Scholar.id == Document.scholar_id)
            .where(
                Document.id == record_id,
                Document.deleted_at.is_(None),
                Scholar.deleted_at.is_(None),
                scope.scholar_predicate(principal, "documents"),
            )
        )
    ).first()
    if row is None:
        raise forbidden()
    return row[0], row[1]


async def _conference(
    session: AsyncSession, principal: Principal, record_id: uuid.UUID
) -> tuple[Conference, Scholar]:
    if not await module_enabled(session, "conferences"):
        raise ApiError(404, "module_disabled", "This feature is not enabled.")
    row = (
        await session.execute(
            select(Conference, Scholar)
            .join(Scholar, Scholar.id == Conference.scholar_id)
            .where(
                Conference.id == record_id,
                Conference.deleted_at.is_(None),
                scope.scholar_predicate(principal, "conferences"),
            )
        )
    ).first()
    if row is None:
        raise forbidden()
    return row[0], row[1]


async def require_write(
    session: AsyncSession, principal: Principal, table: str, record_id: uuid.UUID
) -> None:
    """403/422 unless the caller may change the record (attach or remove its files)."""
    if table == "scholars":
        scholar = await scope.get_scholar_or_403(session, principal, record_id)
        # Reading a scholar is not enough: only an admin over the scholar's unit may attach.
        if not can(principal, "scholars", "update"):
            raise forbidden()
        scope.require_admin_over(principal, await scope.unit_path(session, scholar.unit_id))
        return
    if table == "publications":
        ctx = await items.load_ctx(session, principal, "publication", record_id)
        workflow.assert_editable(principal, ctx)  # author, while draft or sent back
        return
    if table == "conferences":
        conference, _ = await _conference(session, principal, record_id)
        if conference.scholar_id != principal.scholar_id:
            raise forbidden()
        return
    if table == "documents":
        doc, _ = await document_or_403(session, principal, record_id)
        if doc.scholar_id != principal.scholar_id:
            raise forbidden()
        return
    if table == "thesis_submissions":
        # The author's final thesis while editable; the Library's certificate at its step.
        ctx = await thesis.load_thesis(session, principal, record_id)
        if workflow.current_kind(ctx) == "library":
            await workflow.assert_step_field(session, principal, ctx, "library")
        else:
            workflow.assert_editable(principal, ctx)
        return
    if table == "examiner_reports":
        thesis.require_office(principal, "exam_office")
        await thesis.report_ctx(session, principal, record_id)
        return
    if table in THESIS_CHILDREN:
        office = "exam_office" if table == "vivas" else "library"
        thesis.require_office(principal, office)
        await thesis.child_ctx(session, principal, THESIS_CHILDREN[table], record_id)
        return
    raise forbidden()
