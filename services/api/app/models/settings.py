"""University-wide settings, module switches and approval chains (DATABASE.md §3.2)."""

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import CO_SUPERVISION, ITEM_TYPES, MODULE_KEYS, sql_in
from app.models.base import Base, Timestamps


class Settings(Timestamps, Base):
    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_settings_single_row"),
        CheckConstraint(
            f"co_supervision IN ({sql_in(CO_SUPERVISION)})", name="ck_settings_co_supervision"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    co_supervision: Mapped[str] = mapped_column(Text, server_default=text("'off'"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class Module(Timestamps, Base):
    __tablename__ = "modules"
    __table_args__ = (CheckConstraint(f"key IN ({sql_in(MODULE_KEYS)})", name="ck_modules_key"),)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class ApprovalChain(Timestamps, Base):
    __tablename__ = "approval_chains"
    __table_args__ = (
        CheckConstraint(f"item_type IN ({sql_in(ITEM_TYPES)})", name="ck_chains_item_type"),
        CheckConstraint(
            "jsonb_typeof(steps) = 'array' AND jsonb_array_length(steps) > 0",
            name="ck_chains_steps",
        ),
    )

    item_type: Mapped[str] = mapped_column(Text, primary_key=True)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
