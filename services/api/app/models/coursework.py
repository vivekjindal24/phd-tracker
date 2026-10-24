"""Coursework module (DATABASE.md §3.4-3.5): the course catalogue, enrolments with grades, and
the clearance (approvable — state only via app/workflow.py)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, DomainRow
from app.models.workflow import ApprovalColumns, approval_constraints

LIVE = text("deleted_at IS NULL")


class Course(DomainRow, Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("uq_courses_unit_code", "unit_id", "code", unique=True, postgresql_where=LIVE),
        CheckConstraint("credits > 0 AND credits <= 20", name="ck_courses_credits"),
    )

    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    code: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    credits: Mapped[float] = mapped_column(Numeric(3, 1, asdecimal=False))


class Enrolment(DomainRow, Base):
    __tablename__ = "course_enrolments"
    __table_args__ = (
        Index("uq_enrolment_active", "scholar_id", "course_id", unique=True, postgresql_where=LIVE),
        CheckConstraint(
            "grade_points IS NULL OR grade_points BETWEEN 0 AND 10", name="ck_enrolments_points"
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("courses.id"))
    semester: Mapped[str] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(Text)
    grade_points: Mapped[float | None] = mapped_column(Numeric(4, 2, asdecimal=False))


class CourseworkClearance(ApprovalColumns, DomainRow, Base):
    """`credits` and `cgpa` are computed from the enrolments when the Exam Office submits."""

    __tablename__ = "coursework_clearances"
    __table_args__ = (
        *approval_constraints("coursework_clearances"),
        Index("uq_clearance_active", "scholar_id", unique=True, postgresql_where=LIVE),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    credits: Mapped[float | None] = mapped_column(Numeric(4, 1, asdecimal=False))
    cgpa: Mapped[float | None] = mapped_column(Numeric(4, 2, asdecimal=False))
    cleared_on: Mapped[date | None] = mapped_column(Date)
