"""Grants modules (DATABASE.md §3.6, PRD M6-M8): fellowships, funded projects and their
members, and a ledger that records money in and out — it does not pay (PRD §7)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    FELLOWSHIP_SCHEMES,
    FELLOWSHIP_STATUSES,
    LEDGER_HEADS,
    LEDGER_KINDS,
    PROJECT_STATUSES,
    sql_in,
)
from app.models.base import Base, DomainRow
from app.models.org import LIVE

Money = Numeric(12, 2, asdecimal=False)


class Fellowship(DomainRow, Base):
    __tablename__ = "fellowships"
    __table_args__ = (
        CheckConstraint(f"scheme IN ({sql_in(FELLOWSHIP_SCHEMES)})", name="ck_fellowships_scheme"),
        CheckConstraint(f"status IN ({sql_in(FELLOWSHIP_STATUSES)})", name="ck_fellowships_status"),
        CheckConstraint("end_date >= start_date", name="ck_fellowships_dates"),
        CheckConstraint("amount_monthly >= 0 AND hra_amount >= 0", name="ck_fellowships_amounts"),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    scheme: Mapped[str] = mapped_column(Text)
    amount_monthly: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    hra_amount: Mapped[float] = mapped_column(
        Numeric(10, 2, asdecimal=False), server_default=text("0")
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    srf_upgrade_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))


class Project(DomainRow, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in(PROJECT_STATUSES)})", name="ck_projects_status"),
        CheckConstraint("end_date >= start_date", name="ck_projects_dates"),
        CheckConstraint("amount_sanctioned >= 0", name="ck_projects_amount"),
        Index("uq_projects_sanction", "sanction_number", unique=True, postgresql_where=LIVE),
    )

    pi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), index=True
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    agency: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    sanction_number: Mapped[str] = mapped_column(Text)
    amount_sanctioned: Mapped[float] = mapped_column(Money)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default=text("'ongoing'"))


class ProjectMember(DomainRow, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        Index("uq_project_members", "project_id", "scholar_id", unique=True, postgresql_where=LIVE),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )
    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    member_role: Mapped[str] = mapped_column(Text)


class LedgerEntry(DomainRow, Base):
    """Money in (disbursement) or out (expense) against exactly one project or fellowship."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("num_nonnulls(project_id, fellowship_id) = 1", name="ck_ledger_owner"),
        CheckConstraint(f"entry_kind IN ({sql_in(LEDGER_KINDS)})", name="ck_ledger_kind"),
        CheckConstraint(f"head IN ({sql_in(LEDGER_HEADS)})", name="ck_ledger_head"),
        CheckConstraint("amount > 0", name="ck_ledger_amount"),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )
    fellowship_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fellowships.id"), index=True
    )
    entry_kind: Mapped[str] = mapped_column(Text)
    head: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Money)
    entry_date: Mapped[date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, server_default=text("''"))


class UtilisationCertificate(DomainRow, Base):
    """One per reporting period; the signed certificate is attached as a file."""

    __tablename__ = "utilisation_certificates"
    __table_args__ = (CheckConstraint("period_end >= period_start", name="ck_ucs_period"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), index=True
    )
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    submitted_on: Mapped[date | None] = mapped_column(Date)
