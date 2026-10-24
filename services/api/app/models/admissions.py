"""Admissions module (DATABASE.md §3.6): an internal record of admitted candidates — no public
applicant portal (PRD §7). Converting a selected candidate creates their scholar profile."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import ENTRANCE_ROUTES, INTERVIEW_RESULTS, sql_in
from app.models.base import Base, DomainRow


class Admission(DomainRow, Base):
    __tablename__ = "admissions"
    __table_args__ = (
        CheckConstraint(
            f"entrance_route IN ({sql_in(ENTRANCE_ROUTES)})", name="ck_admissions_route"
        ),
        CheckConstraint(
            f"interview_result IN ({sql_in(INTERVIEW_RESULTS)})", name="ck_admissions_result"
        ),
        CheckConstraint(
            "scholar_id IS NULL OR interview_result = 'selected'", name="ck_admissions_converted"
        ),
        Index("uq_admissions_scholar", "scholar_id", unique=True),
        Index(
            "ix_admissions_name_trgm",
            "candidate_name",
            postgresql_using="gin",
            postgresql_ops={"candidate_name": "gin_trgm_ops"},
        ),
    )

    candidate_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT)
    phone: Mapped[str | None] = mapped_column(Text)
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    entrance_route: Mapped[str] = mapped_column(Text)
    entrance_score: Mapped[float | None] = mapped_column(Numeric(6, 2, asdecimal=False))
    interview_date: Mapped[date | None] = mapped_column(Date)
    interview_result: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    admitted_on: Mapped[date | None] = mapped_column(Date)
    scholar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id")
    )
