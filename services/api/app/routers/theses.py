"""Thesis submission (PRD M3, UX Flow 8): the chain itself runs on /items; here the scholar's
draft, the Library's plagiarism fields, the Exam Office's examiners, and everything recorded
after approval — examiner reports, viva, Shodhganga deposit."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import items, scope, thesis, workflow
from app.auth.principal import Principal
from app.crud import insert, update
from app.db import get_session
from app.enums import ItemState
from app.errors import ApiError
from app.models import (
    ExaminerReport,
    Faculty,
    ShodhgangaDeposit,
    ThesisSubmission,
    User,
    Viva,
)
from app.models import Scholar as ScholarRow
from app.modules import require_module
from app.notify import notify
from app.rbac import require_perm
from app.schemas import ItemView
from app.schemas.research import (
    DepositIn,
    EvaluationView,
    ExaminerReportIn,
    ExaminerReportUpdate,
    ExaminersIn,
    PlagiarismIn,
    ThesisIn,
    ThesisRow,
    VivaIn,
    VivaUpdate,
)

router = APIRouter(tags=["thesis"], dependencies=[Depends(require_module("documents"))])
CAN_READ = require_perm("thesis_submissions", "read")


@router.get("/theses", response_model=list[ThesisRow])
async def list_theses(
    state: ItemState | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = (
        select(ThesisSubmission, ScholarRow.id, User.full_name)
        .join(ScholarRow, ScholarRow.id == ThesisSubmission.scholar_id)
        .join(User, User.id == ScholarRow.user_id)
        .where(
            ThesisSubmission.deleted_at.is_(None),
            ScholarRow.deleted_at.is_(None),
            scope.scholar_predicate(principal, "thesis_submissions"),
        )
    )
    if state:
        stmt = stmt.where(ThesisSubmission.state == state)
    rows = await session.execute(stmt.order_by(ThesisSubmission.updated_at.desc()).limit(limit))
    out = []
    for t, sid, name in rows:
        step = t.chain_snapshot[t.current_step]["kind"] if t.current_step is not None else None
        out.append(
            {
                "id": t.id,
                "scholar": {"id": sid, "name": name},
                "title": t.title,
                "state": t.state,
                "waiting_on": workflow.STEP_LABELS[step] if step else None,
                "updated_at": t.updated_at,
            }
        )
    return out


@router.post("/theses", response_model=ItemView, status_code=201)
async def create_thesis(
    body: ThesisIn,
    principal: Principal = Depends(require_perm("thesis_submissions", "create")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if principal.scholar_id is None:
        raise ApiError(403, "forbidden", "Scholars submit their own thesis.")
    row = await insert(
        session, principal, ThesisSubmission(scholar_id=principal.scholar_id, title=body.title)
    )
    await session.commit()
    ctx = await thesis.load_thesis(session, principal, row.id)
    return await items.view(session, principal, ctx)


@router.patch("/theses/{thesis_id}", response_model=ItemView)
async def update_thesis(
    thesis_id: uuid.UUID,
    body: ThesisIn,
    principal: Principal = Depends(require_perm("thesis_submissions", "update")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await thesis.load_thesis(session, principal, thesis_id, lock=True)
    workflow.assert_editable(principal, ctx)
    await update(session, principal, ctx.item, body.model_dump())
    await session.commit()
    return await items.view(session, principal, ctx)


async def _step_fields(session, principal, thesis_id, kind: str, changes: dict) -> dict[str, Any]:
    ctx = await thesis.load_thesis(session, principal, thesis_id, lock=True)
    await workflow.assert_step_field(session, principal, ctx, kind)
    await update(session, principal, ctx.item, changes)
    await session.commit()
    return await items.view(session, principal, ctx)


@router.put("/theses/{thesis_id}/plagiarism", response_model=ItemView)
async def set_plagiarism(
    thesis_id: uuid.UUID,
    body: PlagiarismIn,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Library step only; the certificate is attached to the thesis as a file."""
    return await _step_fields(session, principal, thesis_id, "library", body.model_dump())


@router.put("/theses/{thesis_id}/examiners", response_model=ItemView)
async def set_examiners(
    thesis_id: uuid.UUID,
    body: ExaminersIn,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Exam Office step only; names stay confidential (thesis.py)."""
    return await _step_fields(session, principal, thesis_id, "exam_office", body.model_dump())


@router.get("/theses/{thesis_id}/evaluation", response_model=EvaluationView)
async def get_evaluation(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await thesis.load_thesis(session, principal, thesis_id)
    return await thesis.evaluation(session, principal, ctx)


async def _office_ctx(session, principal, thesis_id: uuid.UUID, office: str):
    thesis.require_office(principal, office)
    ctx = await thesis.load_thesis(session, principal, thesis_id, lock=True)
    thesis.require_approved(ctx)
    return ctx


async def _done(session, principal, ctx) -> dict[str, Any]:
    await session.commit()
    return await thesis.evaluation(session, principal, ctx)


@router.post("/theses/{thesis_id}/examiner-reports", response_model=EvaluationView)
async def add_examiner_report(
    thesis_id: uuid.UUID,
    body: ExaminerReportIn,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await _office_ctx(session, principal, thesis_id, "exam_office")
    await insert(session, principal, ExaminerReport(thesis_id=thesis_id, **body.model_dump()))
    return await _done(session, principal, ctx)


@router.patch("/examiner-reports/{report_id}", response_model=EvaluationView)
async def update_examiner_report(
    report_id: uuid.UUID,
    body: ExaminerReportUpdate,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    thesis.require_office(principal, "exam_office")
    report, ctx = await thesis.report_ctx(session, principal, report_id)
    await update(session, principal, report, body.model_dump(exclude_unset=True))
    return await _done(session, principal, ctx)


async def _guides(
    session: AsyncSession, principal: Principal, scholar: ScholarRow
) -> list[uuid.UUID]:
    """The scholar and their supervisor(s): who learns that reports are out."""
    co = scholar.co_supervisor_id if principal.co_supervision != "off" else None
    fids = [f for f in (scholar.supervisor_id, co) if f]
    users = list(await session.scalars(select(Faculty.user_id).where(Faculty.id.in_(fids))))
    return [scholar.user_id, *users]


@router.post("/theses/{thesis_id}/release-reports", response_model=EvaluationView)
async def release_reports(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await _office_ctx(session, principal, thesis_id, "exam_office")
    pending = [
        r
        for r in await session.scalars(
            select(ExaminerReport).where(
                ExaminerReport.thesis_id == thesis_id,
                ExaminerReport.deleted_at.is_(None),
                ExaminerReport.released_at.is_(None),
            )
        )
    ]
    if not pending:
        raise ApiError(422, "nothing_to_release", "There are no unreleased reports.")
    now = datetime.now(UTC)
    for r in pending:
        await update(session, principal, r, {"released_at": now})
    notify(
        session,
        await _guides(session, principal, ctx.scholar),
        "system",
        "Examiner reports released",
        f"{len(pending)} report(s) on the thesis are now available.",
        ctx.link,
    )
    return await _done(session, principal, ctx)


@router.post("/theses/{thesis_id}/vivas", response_model=EvaluationView)
async def record_viva(
    thesis_id: uuid.UUID,
    body: VivaIn,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    ctx = await _office_ctx(session, principal, thesis_id, "exam_office")
    await insert(session, principal, Viva(thesis_id=thesis_id, **body.model_dump()))
    if body.outcome == "pass":
        await items.advance_stage(session, principal, ctx.scholar, "Viva")
    notify(session, [ctx.scholar.user_id], "system", "Your viva has been recorded", link=ctx.link)
    return await _done(session, principal, ctx)


@router.patch("/vivas/{viva_id}", response_model=EvaluationView)
async def update_viva(
    viva_id: uuid.UUID,
    body: VivaUpdate,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    thesis.require_office(principal, "exam_office")
    viva, ctx = await thesis.child_ctx(session, principal, Viva, viva_id)
    await update(session, principal, viva, body.model_dump(exclude_unset=True))
    if viva.outcome == "pass":
        await items.advance_stage(session, principal, ctx.scholar, "Viva")
    return await _done(session, principal, ctx)


@router.put("/theses/{thesis_id}/deposit", response_model=EvaluationView)
async def record_deposit(
    thesis_id: uuid.UUID,
    body: DepositIn,
    principal: Principal = Depends(CAN_READ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The Library records the Shodhganga deposit — a record, not a sync (PRD §7)."""
    ctx = await _office_ctx(session, principal, thesis_id, "library")
    existing = await session.scalar(
        select(ShodhgangaDeposit).where(
            ShodhgangaDeposit.thesis_id == thesis_id, ShodhgangaDeposit.deleted_at.is_(None)
        )
    )
    if existing:
        await update(session, principal, existing, body.model_dump())
    else:
        await insert(
            session, principal, ShodhgangaDeposit(thesis_id=thesis_id, **body.model_dump())
        )
    return await _done(session, principal, ctx)
