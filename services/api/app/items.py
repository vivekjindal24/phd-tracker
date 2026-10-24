"""Approvable items, generically (PRD F3). Every item type registers here once; the item
page, actions and the approver queue then work for it with no per-type workflow code."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import scope, workflow
from app.auth.principal import Principal
from app.crud import update
from app.enums import STAGES
from app.errors import ApiError, forbidden
from app.models import (
    ApprovalActionRow,
    ApprovalChain,
    FileRow,
    OrgUnit,
    ProgressReport,
    Publication,
    Scholar,
    ThesisSubmission,
    User,
)
from app.modules import module_enabled
from app.workflow import ITEM_LABELS, STEP_LABELS, ItemContext

Hook = Callable[[AsyncSession, Principal, ItemContext], Awaitable[None]]


@dataclass(frozen=True)
class ItemKind:
    model: type
    entity: str  # rbac MATRIX row deciding who may see it at all
    title: Callable[[Any], str]
    content: Callable[[Any, Principal], dict[str, Any]]  # what this viewer may see
    module: str | None = None  # optional module that must be on (PRD F4)
    # step kind -> (column, label) that step must fill in before it may approve
    required: dict[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)
    before_submit: Hook | None = None  # raise to refuse a submit / resubmit
    on_approved: Hook | None = None  # side effects of the final approval


async def advance_stage(
    session: AsyncSession, principal: Principal, scholar: Scholar, stage: str
) -> None:
    """Move a scholar forward to `stage`; never backwards (an admin corrects by hand)."""
    if STAGES.index(stage) > STAGES.index(scholar.stage):
        await update(session, principal, scholar, {"stage": stage})


def _report_title(r: ProgressReport) -> str:
    return f"{r.period.replace('-', '–')} {r.report_year}"  # noqa: RUF001


def _report_content(r: ProgressReport, _: Principal) -> dict[str, Any]:
    return {"report_year": r.report_year, "period": r.period, "summary": r.summary}


def sees_examiners(principal: Principal) -> bool:
    """Examiner identities: Exam Office, Research Office, root admin (PRD M3)."""
    return principal.is_root_admin or bool(
        principal.office_roles & {"exam_office", "research_office"}
    )


def _thesis_content(t: ThesisSubmission, principal: Principal) -> dict[str, Any]:
    names = sees_examiners(principal)
    return {
        "title": t.title,
        "plagiarism_tool": t.plagiarism_tool,
        "plagiarism_score": t.plagiarism_score,
        "examiners": t.examiners if names else None,
        "examiners_entered": t.examiners is not None,
        "examiners_hidden": not names,
    }


async def _thesis_has_file(session: AsyncSession, _: Principal, ctx: ItemContext) -> None:
    files = await session.scalar(
        select(func.count())
        .select_from(FileRow)
        .where(
            FileRow.table_name == "thesis_submissions",
            FileRow.record_id == ctx.item.id,
            FileRow.status == "ready",
            FileRow.deleted_at.is_(None),
        )
    )
    if not files:
        raise workflow.violation("Upload the final thesis file before submitting.")


async def _thesis_approved(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    await advance_stage(session, principal, ctx.scholar, "Thesis Submitted")


def _publication_content(p: Publication, _: Principal) -> dict[str, Any]:
    return {
        "title": p.title,
        "authors": p.authors,
        "pub_type": p.pub_type,
        "venue": p.venue,
        "issn_isbn": p.issn_isbn,
        "indexing": list(p.indexing),
        "doi": p.doi,
        "pub_year": p.pub_year,
        "pub_status": p.pub_status,
    }


REGISTRY: dict[str, ItemKind] = {
    "progress_report": ItemKind(ProgressReport, "progress_reports", _report_title, _report_content),
    "publication": ItemKind(
        Publication, "publications", lambda p: p.title, _publication_content, "publications"
    ),
    "thesis_submission": ItemKind(
        ThesisSubmission,
        "thesis_submissions",
        lambda t: t.title,
        _thesis_content,
        "documents",
        required={
            "library": (
                ("plagiarism_tool", "the plagiarism tool"),
                ("plagiarism_score", "the plagiarism score"),
            ),
            "exam_office": (("examiners", "the examiners"),),
        },
        before_submit=_thesis_has_file,
        on_approved=_thesis_approved,
    ),
}


async def submit(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    kind = kind_of(ctx.item_type)
    if kind.before_submit and workflow.is_initiator(principal, ctx):
        await kind.before_submit(session, principal, ctx)
    await workflow.submit(session, principal, ctx)


async def resubmit(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    kind = kind_of(ctx.item_type)
    if kind.before_submit and workflow.is_initiator(principal, ctx):
        await kind.before_submit(session, principal, ctx)
    await workflow.resubmit(session, principal, ctx)


async def approve(
    session: AsyncSession, principal: Principal, ctx: ItemContext, comment: str | None
) -> None:
    kind = kind_of(ctx.item_type)
    step = workflow.current_kind(ctx)
    missing = [
        label
        for column, label in kind.required.get(step or "", ())
        if getattr(ctx.item, column) in (None, "")
    ]
    if missing and await workflow.can_act(session, principal, ctx):
        raise workflow.violation(f"Fill in {' and '.join(missing)} before approving.")
    await workflow.approve(session, principal, ctx, comment)
    if ctx.item.state == "approved" and kind.on_approved:
        await kind.on_approved(session, principal, ctx)


async def enabled_kinds(session: AsyncSession) -> dict[str, ItemKind]:
    return {
        t: k
        for t, k in REGISTRY.items()
        if k.module is None or await module_enabled(session, k.module)  # type: ignore[arg-type]
    }


def kind_of(item_type: str) -> ItemKind:
    kind = REGISTRY.get(item_type)
    if kind is None:
        raise forbidden()
    return kind


async def load_ctx(
    session: AsyncSession,
    principal: Principal,
    item_type: str,
    item_id: uuid.UUID,
    *,
    lock: bool = False,
) -> ItemContext:
    kind = kind_of(item_type)
    if kind.module and not await module_enabled(session, kind.module):  # type: ignore[arg-type]
        raise ApiError(404, "module_disabled", "This feature is not enabled.")
    stmt = (
        select(kind.model, Scholar, OrgUnit.path)
        .join(Scholar, Scholar.id == kind.model.scholar_id)
        .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
        .where(
            kind.model.id == item_id,
            kind.model.deleted_at.is_(None),
            Scholar.deleted_at.is_(None),
            scope.scholar_predicate(principal, kind.entity),
        )
    )
    if lock:
        stmt = stmt.with_for_update(of=kind.model)  # two approvers clicking at once
    row = (await session.execute(stmt)).first()
    if row is None:
        raise forbidden()
    item, scholar, path = row
    return ItemContext(item_type, item, scholar, path)


async def chain_for(session: AsyncSession, ctx: ItemContext) -> list[dict[str, Any]]:
    if ctx.item.chain_snapshot:
        return list(ctx.item.chain_snapshot)
    chain = await session.get(ApprovalChain, ctx.item_type)  # preview for drafts
    return list(chain.steps) if chain else []


def _initiator_label(item_type: str) -> str:
    return "the scholar" if workflow.INITIATOR[item_type] == "scholar" else "the Exam Office"


async def view(session: AsyncSession, principal: Principal, ctx: ItemContext) -> dict[str, Any]:
    item = ctx.item
    kind = kind_of(ctx.item_type)
    steps = await chain_for(session, ctx)
    current = item.current_step if item.state == "in_review" else None
    done_upto = len(steps) if item.state == "approved" else (current or 0)
    chain = [
        {
            "kind": s["kind"],
            "label": STEP_LABELS[s["kind"]],
            "status": "done" if i < done_upto else "current" if i == current else "upcoming",
        }
        for i, s in enumerate(steps)
    ]
    can_act = await workflow.can_act(session, principal, ctx)
    is_init = workflow.is_initiator(principal, ctx)
    targets = []
    if can_act and current is not None:
        targets = [{"to_step": None, "label": f"Back to {_initiator_label(ctx.item_type)}"}]
        targets += [{"to_step": i, "label": STEP_LABELS[steps[i]["kind"]]} for i in range(current)]
    blocked_reason = None
    kind_now = workflow.current_kind(ctx)
    if kind_now and not can_act and workflow.holds_step(principal, ctx, kind_now):
        blocked_reason = (
            "You acted on the previous step; another approver needs to act on this one."
        )
    scholar_name = await session.scalar(
        select(User.full_name).where(User.id == ctx.scholar.user_id)
    )
    return {
        "item_type": ctx.item_type,
        "id": item.id,
        "label": ITEM_LABELS[ctx.item_type],
        "title": kind.title(item),
        "scholar": {"id": ctx.scholar.id, "name": scholar_name},
        "state": item.state,
        "current_step": current,
        "waiting_on": STEP_LABELS[kind_now] if kind_now else None,
        "chain": chain,
        "submitted_at": item.submitted_at,
        "approved_at": item.approved_at,
        "content": kind.content(item, principal),
        "can_edit": item.state in ("draft", "sent_back") and is_init,
        "can_submit": item.state == "draft" and is_init,
        "can_resubmit": item.state == "sent_back" and is_init,
        "can_act": can_act,
        "send_back_targets": targets,
        "blocked_reason": blocked_reason,
        "history": await history(session, ctx),
    }


async def history(session: AsyncSession, ctx: ItemContext) -> list[dict[str, Any]]:
    rows = await session.execute(
        select(ApprovalActionRow, User.full_name)
        .join(User, User.id == ApprovalActionRow.actor_id)
        .where(
            ApprovalActionRow.item_type == ctx.item_type, ApprovalActionRow.item_id == ctx.item.id
        )
        .order_by(ApprovalActionRow.at)
    )
    steps = ctx.item.chain_snapshot or []
    out = []
    for a, actor in rows:
        to = None
        if a.action == "send_back":
            to = (
                STEP_LABELS[steps[a.to_step]["kind"]]
                if a.to_step is not None
                else _initiator_label(ctx.item_type)
            )
        out.append(
            {
                "action": a.action,
                "actor": actor,
                "step": STEP_LABELS[a.step_kind] if a.step_kind else None,
                "to": to,
                "comment": a.comment,
                "at": a.at,
            }
        )
    return out


async def queue(session: AsyncSession, principal: Principal) -> list[dict[str, Any]]:
    """Items waiting at a step the caller can act on, oldest first."""
    # ponytail: loads every visible in-review item then filters with can_act in Python —
    # fine at university scale (hundreds); push the step resolution into SQL if it grows.
    out = []
    for item_type, kind in (await enabled_kinds(session)).items():
        rows = await session.execute(
            select(kind.model, Scholar, OrgUnit.path, User.full_name)
            .join(Scholar, Scholar.id == kind.model.scholar_id)
            .join(OrgUnit, OrgUnit.id == Scholar.unit_id)
            .join(User, User.id == Scholar.user_id)
            .where(
                kind.model.state == "in_review",
                kind.model.deleted_at.is_(None),
                scope.scholar_predicate(principal, kind.entity),
            )
        )
        for item, scholar, path, name in rows:
            ctx = ItemContext(item_type, item, scholar, path)
            if not await workflow.can_act(session, principal, ctx):
                continue
            since = (
                await session.scalar(
                    select(func.max(ApprovalActionRow.at)).where(
                        ApprovalActionRow.item_type == item_type,
                        ApprovalActionRow.item_id == item.id,
                    )
                )
                or item.submitted_at
                or item.created_at
            )
            out.append(
                {
                    "item_type": item_type,
                    "id": item.id,
                    "label": ITEM_LABELS[item_type],
                    "title": kind.title(item),
                    "scholar": {"id": scholar.id, "name": name},
                    "step": STEP_LABELS[workflow.current_kind(ctx)],
                    "waiting_since": since,
                    "days_waiting": (datetime.now(UTC) - since).days,
                }
            )
    return sorted(out, key=lambda q: q["waiting_since"])
