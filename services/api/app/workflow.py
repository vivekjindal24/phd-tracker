"""The one approval engine for every approvable item type (PRD F3, SECURITY.md §4).

States: draft -> in_review(step i) -> ... -> approved, plus sent_back. The chain is copied
onto the item at submit (chain_snapshot), so later chain edits never touch in-flight items.
State changes ONLY here."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.crud import audit, snapshot
from app.enums import INITIATOR, OFFICE_ROLES
from app.errors import ApiError
from app.models import (
    ApprovalActionRow,
    ApprovalChain,
    Faculty,
    OrgUnit,
    RoleAssignment,
    Scholar,
    Settings,
)
from app.models.base import Ltree
from app.notify import notify

ITEM_LABELS = {
    "progress_report": "Progress report",
    "publication": "Publication",
    "coursework_clearance": "Coursework clearance",
    "thesis_submission": "Thesis submission",
    "no_dues_clearance": "No-dues clearance",
}
STEP_LABELS = {
    "supervisor": "Supervisor",
    "department": "Department",
    "research_office": "Research Office",
    "exam_office": "Exam Office",
    "library": "Library",
}


class Approvable(Protocol):
    id: uuid.UUID
    state: str
    current_step: int | None
    chain_snapshot: list[dict[str, Any]] | None
    submitted_at: datetime | None
    approved_at: datetime | None
    __tablename__: str


@dataclass(frozen=True)
class ItemContext:
    item_type: str
    item: Approvable
    scholar: Scholar
    scholar_unit_path: str

    @property
    def link(self) -> str:
        return f"/items/{self.item_type}/{self.item.id}"

    @property
    def label(self) -> str:
        return ITEM_LABELS[self.item_type]


def violation(message: str) -> ApiError:
    return ApiError(422, "workflow_violation", message)


def current_kind(ctx: ItemContext) -> str | None:
    item = ctx.item
    if item.state != "in_review" or item.current_step is None or not item.chain_snapshot:
        return None
    return item.chain_snapshot[item.current_step]["kind"]


def is_initiator(principal: Principal, ctx: ItemContext) -> bool:
    if INITIATOR[ctx.item_type] == "scholar":
        return principal.scholar_id == ctx.scholar.id
    return INITIATOR[ctx.item_type] in principal.office_roles


def holds_step(principal: Principal, ctx: ItemContext, kind: str) -> bool:
    """Role-level answer: does the caller fill a step of this kind for this scholar?"""
    if principal.user_id == ctx.scholar.user_id:
        return False  # no self-approval
    if kind == "supervisor":
        fid = principal.faculty_id
        return fid is not None and (
            ctx.scholar.supervisor_id == fid
            or (principal.co_supervision == "approve" and ctx.scholar.co_supervisor_id == fid)
        )
    if kind == "department":
        path = ctx.scholar_unit_path
        return principal.covers("unit_head", path) or principal.covers("admin", path)
    return kind in OFFICE_ROLES and kind in principal.office_roles


async def _last_action(session: AsyncSession, ctx: ItemContext) -> ApprovalActionRow | None:
    return await session.scalar(
        select(ApprovalActionRow)
        .where(
            ApprovalActionRow.item_type == ctx.item_type,
            ApprovalActionRow.item_id == ctx.item.id,
        )
        .order_by(ApprovalActionRow.at.desc(), ApprovalActionRow.id.desc())
        .limit(1)
    )


async def can_act(session: AsyncSession, principal: Principal, ctx: ItemContext) -> bool:
    kind = current_kind(ctx)
    if kind is None or not holds_step(principal, ctx, kind):
        return False
    last = await _last_action(session, ctx)
    # No one approves two consecutive steps of the same item (SECURITY.md §4).
    return not (last and last.action == "approve" and last.actor_id == principal.user_id)


def assert_editable(principal: Principal, ctx: ItemContext) -> None:
    if ctx.item.state not in ("draft", "sent_back") or not is_initiator(principal, ctx):
        raise violation(
            "This item can only be edited by its author while it is a draft or has been sent back."
        )


async def assert_step_field(
    session: AsyncSession, principal: Principal, ctx: ItemContext, kind: str
) -> None:
    """Step-only fields (e.g. plagiarism score) are writable only by that step's actor."""
    if current_kind(ctx) != kind or not await can_act(session, principal, ctx):
        raise violation(f"Only the {STEP_LABELS[kind]} step can change this field.")


async def step_actor_ids(
    session: AsyncSession, ctx: ItemContext, kind: str, actor: uuid.UUID
) -> list[uuid.UUID]:
    """Who to notify when an item reaches a step of this kind — never the actor who sent it
    there, who may not act on two steps in a row anyway."""
    if kind == "supervisor":
        fids = [ctx.scholar.supervisor_id]
        if await _co_supervision(session) == "approve":
            fids.append(ctx.scholar.co_supervisor_id)
        rows = await session.scalars(
            select(Faculty.user_id).where(Faculty.id.in_([f for f in fids if f]))
        )
        return [u for u in rows if u != actor]
    if kind == "department":
        # Nearest unit at or above the scholar's with a head or admin other than the actor: a
        # HoD who just approved as supervisor hands the step to the Dean, not to themselves.
        rows = (
            await session.execute(
                select(RoleAssignment.user_id, func.nlevel(OrgUnit.path))
                .join(OrgUnit, OrgUnit.id == RoleAssignment.unit_id)
                .where(
                    RoleAssignment.deleted_at.is_(None),
                    RoleAssignment.role.in_(("unit_head", "admin")),
                    RoleAssignment.user_id != actor,
                    OrgUnit.path.op("@>")(cast(literal(ctx.scholar_unit_path), Ltree)),
                )
            )
        ).all()
        if not rows:
            return []
        nearest = max(level for _, level in rows)
        return [uid for uid, level in rows if level == nearest]
    rows = await session.scalars(
        select(RoleAssignment.user_id).where(
            RoleAssignment.role == kind,
            RoleAssignment.deleted_at.is_(None),
            RoleAssignment.user_id != actor,
        )
    )
    return list(rows)


async def _co_supervision(session: AsyncSession) -> str:
    return await session.scalar(select(Settings.co_supervision).where(Settings.id == 1)) or "off"


def _record(
    session: AsyncSession,
    principal: Principal,
    ctx: ItemContext,
    action: str,
    step_index: int | None,
    to_step: int | None = None,
    comment: str | None = None,
) -> None:
    kind = None
    if step_index is not None and ctx.item.chain_snapshot:
        kind = ctx.item.chain_snapshot[step_index]["kind"]
    session.add(
        ApprovalActionRow(
            item_type=ctx.item_type,
            item_id=ctx.item.id,
            step_index=step_index,
            step_kind=kind,
            action=action,
            to_step=to_step,
            comment=comment,
            actor_id=principal.user_id,
        )
    )


async def _transition(
    session: AsyncSession,
    principal: Principal,
    ctx: ItemContext,
    action: str,
    changes: dict[str, Any],
    step_index: int | None,
    to_step: int | None = None,
    comment: str | None = None,
) -> None:
    prev = snapshot(ctx.item)  # type: ignore[arg-type]
    from_state = ctx.item.state
    for key, value in changes.items():
        setattr(ctx.item, key, value)
    _record(session, principal, ctx, action, step_index, to_step, comment)
    await session.flush()
    await session.refresh(ctx.item)
    audit(
        session,
        principal,
        ctx.item,
        "transition",
        prev=prev,  # type: ignore[arg-type]
        from_state=from_state,
        to_state=ctx.item.state,
    )


async def _notify_step(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    kind = current_kind(ctx)
    if kind is None:
        return
    ids = await step_actor_ids(session, ctx, kind, principal.user_id)
    notify(
        session,
        ids,
        "approval_waiting",
        f"{ctx.label} waiting for you",
        f"{STEP_LABELS[kind]} step",
        ctx.link,
    )


async def submit(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    if ctx.item.state != "draft" or not is_initiator(principal, ctx):
        raise violation("Only the author can submit a draft.")
    chain = await session.get(ApprovalChain, ctx.item_type)
    if chain is None:
        raise ApiError(500, "chain_missing", f"No approval chain configured for {ctx.label}.")
    await _transition(
        session,
        principal,
        ctx,
        "submit",
        {
            "chain_snapshot": list(chain.steps),
            "state": "in_review",
            "current_step": 0,
            "submitted_at": datetime.now(UTC),
        },
        step_index=None,
    )
    await _notify_step(session, principal, ctx)


async def resubmit(session: AsyncSession, principal: Principal, ctx: ItemContext) -> None:
    """A sent-back item restarts from step 1, using the snapshot taken at first submit."""
    if ctx.item.state != "sent_back" or not is_initiator(principal, ctx):
        raise violation("Only the author can resubmit an item that was sent back.")
    await _transition(
        session,
        principal,
        ctx,
        "resubmit",
        {"state": "in_review", "current_step": 0},
        step_index=None,
    )
    await _notify_step(session, principal, ctx)


async def approve(
    session: AsyncSession, principal: Principal, ctx: ItemContext, comment: str | None = None
) -> None:
    if not await can_act(session, principal, ctx):
        raise violation("You cannot approve this item at its current step.")
    step = ctx.item.current_step
    assert step is not None and ctx.item.chain_snapshot is not None
    if step + 1 < len(ctx.item.chain_snapshot):
        await _transition(
            session,
            principal,
            ctx,
            "approve",
            {"current_step": step + 1},
            step_index=step,
            comment=comment,
        )
        await _notify_step(session, principal, ctx)
        return
    await _transition(
        session,
        principal,
        ctx,
        "approve",
        {
            "state": "approved",
            "current_step": None,
            "approved_at": datetime.now(UTC),
        },
        step_index=step,
        comment=comment,
    )
    notify(session, [ctx.scholar.user_id], "approved", f"{ctx.label} approved", link=ctx.link)


async def send_back(
    session: AsyncSession,
    principal: Principal,
    ctx: ItemContext,
    comment: str,
    to_step: int | None = None,
) -> None:
    """to_step=None sends back to the initiator; otherwise to any earlier step."""
    if not comment.strip():
        raise violation("A reason is required when sending back.")
    if not await can_act(session, principal, ctx):
        raise violation("You cannot send back this item at its current step.")
    step = ctx.item.current_step
    assert step is not None
    if to_step is None:
        await _transition(
            session,
            principal,
            ctx,
            "send_back",
            {"state": "sent_back", "current_step": None},
            step_index=step,
            comment=comment,
        )
        # Whoever resubmits hears about it: the scholar, or the office that started the item.
        initiator = INITIATOR[ctx.item_type]
        if initiator == "scholar":
            ids = [ctx.scholar.user_id]
        else:
            ids = await step_actor_ids(session, ctx, initiator, principal.user_id)
        notify(session, ids, "sent_back", f"{ctx.label} sent back", comment, ctx.link)
        return
    if not 0 <= to_step < step:
        raise violation("An item can only be sent back to an earlier step.")
    await _transition(
        session,
        principal,
        ctx,
        "send_back",
        {"current_step": to_step},
        step_index=step,
        to_step=to_step,
        comment=comment,
    )
    kind = ctx.item.chain_snapshot[to_step]["kind"]  # type: ignore[index]
    ids = await step_actor_ids(session, ctx, kind, principal.user_id)
    notify(
        session,
        ids,
        "sent_back",
        f"{ctx.label} sent back to {STEP_LABELS[kind]}",
        comment,
        ctx.link,
    )
