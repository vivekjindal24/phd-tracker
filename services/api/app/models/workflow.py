"""Approval columns shared by every approvable table, and the action history
(DATABASE.md §3.4). State changes only through app/workflow.py."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import APPROVAL_ACTIONS, ITEM_STATES, ITEM_TYPES, STEP_KINDS, sql_in
from app.models.base import Base


class ApprovalColumns:
    state: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    current_step: Mapped[int | None] = mapped_column(Integer)
    chain_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def approval_constraints(table: str) -> tuple[CheckConstraint, ...]:
    """CHECKs every approvable table carries: valid state; step set iff in_review."""
    return (
        CheckConstraint(f"state IN ({sql_in(ITEM_STATES)})", name=f"ck_{table}_state"),
        CheckConstraint(
            "(current_step IS NOT NULL) = (state = 'in_review')", name=f"ck_{table}_step"
        ),
    )


class ApprovalActionRow(Base):
    __tablename__ = "approval_actions"
    __table_args__ = (
        CheckConstraint(f"item_type IN ({sql_in(ITEM_TYPES)})", name="ck_actions_item_type"),
        CheckConstraint(f"action IN ({sql_in(APPROVAL_ACTIONS)})", name="ck_actions_action"),
        CheckConstraint(
            f"step_kind IS NULL OR step_kind IN ({sql_in(STEP_KINDS)})",
            name="ck_actions_step_kind",
        ),
        CheckConstraint(
            "action <> 'send_back' OR char_length(coalesce(comment, '')) > 0",
            name="ck_actions_send_back_comment",
        ),
        Index("ix_approval_actions_item", "item_type", "item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    item_type: Mapped[str] = mapped_column(Text)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    step_index: Mapped[int | None] = mapped_column(Integer)
    step_kind: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    to_step: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # clock_timestamp, not now(): several actions in one transaction must still order.
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
