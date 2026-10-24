"""University-wide settings, module switches and approval chains (DATABASE.md §3.2)."""

import json
import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    CO_SUPERVISION,
    DEFAULT_RUBRIC,
    ITEM_TYPES,
    MODULE_KEYS,
    SEMINAR_GRADERS,
    sql_in,
)
from app.models.base import Base, Timestamps


class Settings(Timestamps, Base):
    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_settings_single_row"),
        CheckConstraint(
            f"co_supervision IN ({sql_in(CO_SUPERVISION)})", name="ck_settings_co_supervision"
        ),
        CheckConstraint(
            f"seminar_graders IN ({sql_in(SEMINAR_GRADERS)})", name="ck_settings_seminar_graders"
        ),
        CheckConstraint(
            "jsonb_typeof(seminar_rubric) = 'array' AND jsonb_array_length(seminar_rubric) > 0",
            name="ck_settings_seminar_rubric",
        ),
        CheckConstraint("min_coursework_credits BETWEEN 0 AND 40", name="ck_settings_min_credits"),
        CheckConstraint("min_coursework_cgpa BETWEEN 0 AND 10", name="ck_settings_min_cgpa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    co_supervision: Mapped[str] = mapped_column(Text, server_default=text("'off'"))
    require_hardcopy: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    seminar_graders: Mapped[str] = mapped_column(Text, server_default=text("'panel'"))
    seminar_rubric: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text(f"'{json.dumps(list(DEFAULT_RUBRIC))}'::jsonb")
    )
    # UGC 2022: coursework of 12-16 credits, passed with 55% or its grade equivalent.
    min_coursework_credits: Mapped[float] = mapped_column(
        Numeric(3, 1, asdecimal=False), server_default=text("12")
    )
    min_coursework_cgpa: Mapped[float] = mapped_column(
        Numeric(4, 2, asdecimal=False), server_default=text("5.5")
    )
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
