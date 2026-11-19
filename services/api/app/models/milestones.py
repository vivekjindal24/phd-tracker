"""The RDC / committee register (DATABASE.md §3.3)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    APPROVAL_BODIES,
    COMMITTEE_ROLES,
    COMMITTEE_SEATS,
    MILESTONE_STATUSES,
    MILESTONE_TYPES,
    sql_in,
)
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


class CommitteeFormation(DomainRow, Base):
    """One version of a committee (PRD F9b): a scholar's Research Advisory Committee, or a
    department's research committee. The latest is the current committee; earlier ones are
    history, each printed as its own form."""

    __tablename__ = "committee_formations"
    __table_args__ = (
        CheckConstraint(
            "(scholar_id IS NULL) <> (unit_id IS NULL)", name="ck_committee_formation_owner"
        ),
    )

    scholar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    formed_on: Mapped[date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    # An advisory committee's supervisor when it was formed: the secretary on its form.
    secretary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id")
    )


class CommitteeMember(DomainRow, Base):
    """One member of a committee formation: faculty of this university, a scholar (on a
    department's committee), or an outside expert by name (PRD F9b). An advisory committee's
    supervisor is its secretary and never a row here."""

    __tablename__ = "committee_members"
    __table_args__ = (
        CheckConstraint(
            "(faculty_id IS NOT NULL AND scholar_member_id IS NULL"
            " AND name IS NULL AND institution IS NULL)"
            " OR (scholar_member_id IS NOT NULL AND faculty_id IS NULL"
            " AND name IS NULL AND institution IS NULL)"
            " OR (faculty_id IS NULL AND scholar_member_id IS NULL"
            " AND name IS NOT NULL AND institution IS NOT NULL)",
            name="ck_committee_member_kind",
        ),
        CheckConstraint(f"role IN ({sql_in(COMMITTEE_ROLES)})", name="ck_committee_member_role"),
        CheckConstraint(f"seat IN ({sql_in(COMMITTEE_SEATS)})", name="ck_committee_member_seat"),
        Index(
            "uq_committee_member",
            "formation_id",
            "faculty_id",
            unique=True,
            postgresql_where=LIVE,
        ),
        Index(
            "uq_committee_scholar_member",
            "formation_id",
            "scholar_member_id",
            unique=True,
            postgresql_where=LIVE,
        ),
        Index(
            "uq_committee_chair",
            "formation_id",
            unique=True,
            postgresql_where=text("role = 'chairperson' AND deleted_at IS NULL"),
        ),
        Index(
            "uq_committee_secretary",
            "formation_id",
            unique=True,
            postgresql_where=text("role = 'secretary' AND deleted_at IS NULL"),
        ),
    )

    formation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("committee_formations.id"), index=True
    )
    role: Mapped[str] = mapped_column(Text, server_default=text("'member'"))
    seat: Mapped[str | None] = mapped_column(Text)  # department committees only
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id")
    )
    scholar_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id")
    )
    name: Mapped[str | None] = mapped_column(Text)
    institution: Mapped[str | None] = mapped_column(Text)
