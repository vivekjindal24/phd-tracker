"""After the thesis is approved (PRD M3): examiner reports, viva, Shodhganga deposit — and the
confidentiality rules around them, computed here and nowhere else (SECURITY.md §3 †).

- Examiner names (and institutions) reach only the Exam Office, Research Office and root admin
  until a viva has been recorded.
- Reports reach the scholar and their supervisor(s) only once the Exam Office releases them;
  the other roles that can read the thesis (unit heads/admins over it, the offices) see them
  as they arrive, still without names."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items
from app.auth.principal import Principal
from app.errors import ApiError, forbidden
from app.models import ExaminerReport, ShodhgangaDeposit, ThesisSubmission, Viva
from app.workflow import ItemContext

OFFICES_SEEING_UNRELEASED = frozenset({"exam_office", "research_office", "library"})


def sees_unreleased(principal: Principal, ctx: ItemContext) -> bool:
    if principal.office_roles & OFFICES_SEEING_UNRELEASED:
        return True
    path = ctx.scholar_unit_path
    return principal.covers("unit_head", path) or principal.covers("admin", path)


def require_approved(ctx: ItemContext) -> None:
    if ctx.item.state != "approved":
        raise ApiError(
            422,
            "thesis_not_approved",
            "This is recorded once the thesis submission is approved.",
        )


def require_office(principal: Principal, office: str) -> None:
    if office not in principal.office_roles:
        raise forbidden()


async def load_thesis(
    session: AsyncSession, principal: Principal, thesis_id: uuid.UUID, *, lock: bool = False
) -> ItemContext:
    return await items.load_ctx(session, principal, "thesis_submission", thesis_id, lock=lock)


async def _rows(session: AsyncSession, model: type, thesis_id: uuid.UUID) -> list[Any]:
    return list(
        await session.scalars(
            select(model).where(model.thesis_id == thesis_id, model.deleted_at.is_(None))
        )
    )


async def viva_recorded(session: AsyncSession, thesis_id: uuid.UUID) -> bool:
    return bool(await _rows(session, Viva, thesis_id))


async def report_ctx(
    session: AsyncSession, principal: Principal, report_id: uuid.UUID
) -> tuple[ExaminerReport, ItemContext]:
    """An examiner report the caller may read (released, or a role that sees unreleased)."""
    report = await session.scalar(
        select(ExaminerReport).where(
            ExaminerReport.id == report_id, ExaminerReport.deleted_at.is_(None)
        )
    )
    if report is None:
        raise forbidden()
    ctx = await load_thesis(session, principal, report.thesis_id)
    if report.released_at is None and not sees_unreleased(principal, ctx):
        raise forbidden()
    return report, ctx


async def child_ctx(
    session: AsyncSession, principal: Principal, model: type, row_id: uuid.UUID
) -> tuple[Any, ItemContext]:
    """A viva or deposit row: readable by everyone who may read its thesis."""
    row = await session.scalar(select(model).where(model.id == row_id, model.deleted_at.is_(None)))
    if row is None:
        raise forbidden()
    return row, await load_thesis(session, principal, row.thesis_id)


async def evaluation(session: AsyncSession, principal: Principal, ctx: ItemContext) -> dict:
    thesis: ThesisSubmission = ctx.item  # type: ignore[assignment]
    reports = sorted(await _rows(session, ExaminerReport, thesis.id), key=lambda r: r.received_on)
    vivas = sorted(await _rows(session, Viva, thesis.id), key=lambda v: v.held_on)
    deposits = await _rows(session, ShodhgangaDeposit, thesis.id)
    names = items.sees_examiners(principal) or bool(vivas)
    unreleased_ok = sees_unreleased(principal, ctx)
    approved = thesis.state == "approved"
    return {
        "thesis_id": thesis.id,
        "names_hidden": not names,
        "reports": [
            {
                "id": r.id,
                "examiner_name": r.examiner_name if names else None,
                "institution": r.institution if names else None,
                "received_on": r.received_on,
                "recommendation": r.recommendation,
                "notes": r.notes,
                "released": r.released_at is not None,
            }
            for r in reports
            if r.released_at is not None or unreleased_ok
        ],
        "unreleased_count": sum(r.released_at is None for r in reports) if unreleased_ok else 0,
        "vivas": [
            {
                "id": v.id,
                "held_on": v.held_on,
                "venue": v.venue,
                "panel": v.panel,
                "outcome": v.outcome,
                "notes": v.notes,
            }
            for v in vivas
        ],
        "deposit": (
            {
                "id": deposits[0].id,
                "deposited_on": deposits[0].deposited_on,
                "handle_url": deposits[0].handle_url,
            }
            if deposits
            else None
        ),
        "can_record_reports": approved and "exam_office" in principal.office_roles,
        "can_record_viva": approved and "exam_office" in principal.office_roles,
        "can_record_deposit": approved and "library" in principal.office_roles,
    }
