"""The RDC / committee register (DATABASE.md §3.3)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import APPROVAL_BODIES, MILESTONE_STATUSES, MILESTONE_TYPES, sql_in
from app.models.base import Base, DomainRow
from app.models.org import LIVE


class Milestone(DomainRow, Base):
    __tablename__ = "milestones"
    __table_args__ = (
        CheckConstraint(
            f"milestone_type IN ({sql_in(MILESTONE_TYPES)})", name="ck_milestones_type"
        ),
        CheckConstraint(f"status IN ({sql_in(MILESTONE_STATUSES)})", name="ck_milestones_status"),
        CheckConstraint(f"approval_body IN ({sql_in(APPROVAL_BODIES)})", name="ck_milestones_body"),
        Index(
            "ix_milestones_resolution_trgm",
            "resolution_number",
            postgresql_using="gin",
            postgresql_ops={"resolution_number": "gin_trgm_ops"},
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    milestone_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'Pending'"))
    approval_body: Mapped[str] = mapped_column(Text)
    resolution_number: Mapped[str | None] = mapped_column(Text)
    resolution_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    # On proposal approvals only: the one title the thesis and certificate use (thesis.py).
    approved_title: Mapped[str | None] = mapped_column(Text)


class CommitteeMember(DomainRow, Base):
    """One member of a scholar's Research Advisory Committee besides the supervisor, who
    convenes it: faculty of this university, or an outside expert by name (PRD F9b)."""

    __tablename__ = "committee_members"
    __table_args__ = (
        CheckConstraint(
            "(faculty_id IS NOT NULL AND name IS NULL AND institution IS NULL)"
            " OR (faculty_id IS NULL AND name IS NOT NULL AND institution IS NOT NULL)",
            name="ck_committee_member_kind",
        ),
        Index(
            "uq_committee_member", "scholar_id", "faculty_id", unique=True, postgresql_where=LIVE
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id")
    )
    name: Mapped[str | None] = mapped_column(Text)
    institution: Mapped[str | None] = mapped_column(Text)
