"""Progress seminars — the six-monthly review (DATABASE.md §3.3b, PRD F15)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    PANEL_KINDS,
    PERIODS,
    SEMINAR_STATUSES,
    TODO_PARTS,
    TODO_STATUSES,
    sql_in,
)
from app.models.base import Base, DomainRow

LIVE = text("deleted_at IS NULL")


class Seminar(DomainRow, Base):
    __tablename__ = "seminars"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(SEMINAR_STATUSES)})", name="ck_seminars_status"),
        CheckConstraint(f"period IN ({sql_in(PERIODS)})", name="ck_seminars_period"),
        CheckConstraint("report_year BETWEEN 2000 AND 2100", name="ck_seminars_year"),
    )

    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str] = mapped_column(Text, server_default=text("''"))
    report_due: Mapped[date] = mapped_column(Date)
    report_year: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'scheduled'"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class SeminarScholar(DomainRow, Base):
    __tablename__ = "seminar_scholars"
    __table_args__ = (
        Index("uq_seminar_scholar", "seminar_id", "scholar_id", unique=True, postgresql_where=LIVE),
    )

    seminar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seminars.id"), index=True
    )
    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    hardcopy_received_on: Mapped[date | None] = mapped_column(Date)
    draft_points: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    finalised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalised_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )


class SeminarPanel(DomainRow, Base):
    __tablename__ = "seminar_panel"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(PANEL_KINDS)})", name="ck_seminar_panel_kind"),
        Index("uq_seminar_panel", "seminar_id", "faculty_id", unique=True, postgresql_where=LIVE),
    )

    seminar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seminars.id"), index=True
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), index=True
    )
    kind: Mapped[str] = mapped_column(Text, server_default=text("'panel'"))


class SeminarGrade(DomainRow, Base):
    __tablename__ = "seminar_grades"
    __table_args__ = (
        Index(
            "uq_seminar_grade",
            "seminar_scholar_id",
            "grader_id",
            unique=True,
            postgresql_where=LIVE,
        ),
    )

    seminar_scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seminar_scholars.id"), index=True
    )
    grader_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("faculty.id"))
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rubric: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # snapshot at grading time
    comment: Mapped[str] = mapped_column(Text, server_default=text("''"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Todo(DomainRow, Base):
    __tablename__ = "todos"
    __table_args__ = (
        CheckConstraint(f"part IN ({sql_in(TODO_PARTS)})", name="ck_todos_part"),
        CheckConstraint(f"status IN ({sql_in(TODO_STATUSES)})", name="ck_todos_status"),
        CheckConstraint("char_length(text) BETWEEN 1 AND 1000", name="ck_todos_text"),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    part: Mapped[str] = mapped_column(Text)
    # Keep `status` above `text`: the `text` column shadows sqlalchemy.text in this class body.
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    text: Mapped[str] = mapped_column(Text)
    source_seminar_scholar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seminar_scholars.id")
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
