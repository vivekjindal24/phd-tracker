"""All tables, one schema (`core`), one file. Soft-delete only: every query filters deleted_at IS NULL.

Email columns are TEXT here but citext in the DB (migration DDL) — citext lowers
on compare so uniqueness is case-insensitive without app code.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
	pass


class SoftDeleteMixin:
	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
	)
	created_at: Mapped[datetime] = mapped_column(server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
	deleted_at: Mapped[datetime | None] = mapped_column(default=None)


class User(SoftDeleteMixin, Base):
	__tablename__ = "users"
	__table_args__ = (
		CheckConstraint("role IN ('scholar', 'supervisor', 'admin')", name="ck_users_role"),
		{"schema": "core"},
	)

	email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
	password_hash: Mapped[str] = mapped_column(Text, nullable=False)
	full_name: Mapped[str] = mapped_column(Text, nullable=False)
	role: Mapped[str] = mapped_column(Text, nullable=False)


class Supervisor(SoftDeleteMixin, Base):
	__tablename__ = "supervisors"
	__table_args__ = (
		CheckConstraint(
			"designation IN ('Professor', 'Associate Professor', 'Assistant Professor')",
			name="ck_supervisors_designation",
		),
		{"schema": "core"},
	)

	user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("core.users.id"), unique=True)
	full_name: Mapped[str] = mapped_column(Text, nullable=False)
	email: Mapped[str] = mapped_column(Text, nullable=False)
	department: Mapped[str] = mapped_column(Text, nullable=False)
	designation: Mapped[str] = mapped_column(Text, nullable=False)
	max_scholars: Mapped[int] = mapped_column(Integer, nullable=False, default=8)


class Scholar(SoftDeleteMixin, Base):
	__tablename__ = "scholars"
	__table_args__ = (
		CheckConstraint(
			"stage IN ('Registered', 'Coursework', 'Proposal Approved', 'Research Phase', "
			"'Pre-Synopsis Done', 'Thesis Submitted', 'Viva Voce', 'Degree Awarded')",
			name="ck_scholars_stage",
		),
		{"schema": "core"},
	)

	user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("core.users.id"), unique=True)
	scholar_name: Mapped[str] = mapped_column(Text, nullable=False)
	roll_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
	scholar_email: Mapped[str | None] = mapped_column(Text)
	department: Mapped[str] = mapped_column(Text, nullable=False)
	admission_date: Mapped[date] = mapped_column(Date, nullable=False)
	stage: Mapped[str] = mapped_column(Text, nullable=False, default="Registered")
	github_url: Mapped[str | None] = mapped_column(Text)
	supervisor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("core.supervisors.id"))


class Meeting(SoftDeleteMixin, Base):
	__tablename__ = "meetings"
	__table_args__ = ({"schema": "core"},)

	scholar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.scholars.id"), nullable=False)
	supervisor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.supervisors.id"), nullable=False)
	meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
	agenda: Mapped[str | None] = mapped_column(Text)
	minutes: Mapped[str | None] = mapped_column(Text)
	action_items: Mapped[str | None] = mapped_column(Text)
	next_meeting_date: Mapped[date | None] = mapped_column(Date)


class ProgressReport(SoftDeleteMixin, Base):
	__tablename__ = "progress_reports"
	__table_args__ = (
		CheckConstraint("report_year BETWEEN 2000 AND 2100", name="ck_reports_year"),
		CheckConstraint("period IN ('January-June', 'July-December')", name="ck_reports_period"),
		CheckConstraint("state IN ('draft', 'submitted', 'approved', 'rejected')", name="ck_reports_state"),
		# The real duplicate-APR constraint: unique among live rows only, so a
		# soft-deleted report never blocks a legitimate re-creation.
		Index(
			"uq_apr_active",
			"scholar_id",
			"report_year",
			"period",
			unique=True,
			postgresql_where=text("deleted_at IS NULL"),
		),
		{"schema": "core"},
	)

	scholar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.scholars.id"), nullable=False)
	report_year: Mapped[int] = mapped_column(Integer, nullable=False)
	period: Mapped[str] = mapped_column(Text, nullable=False)
	summary: Mapped[str] = mapped_column(Text, nullable=False)
	supervisor_comment: Mapped[str | None] = mapped_column(Text)
	approved_on: Mapped[date | None] = mapped_column(Date)
	state: Mapped[str] = mapped_column(Text, nullable=False, default="draft")


class Milestone(SoftDeleteMixin, Base):
	__tablename__ = "milestones"
	__table_args__ = (
		CheckConstraint(
			"milestone_type IN ('Coursework Completion', 'Proposal Approval (RDC)', "
			"'Pre-Synopsis Seminar', 'Thesis Submission', 'Viva Voce', 'Degree Awarded')",
			name="ck_milestones_type",
		),
		CheckConstraint("status IN ('Pending', 'Approved', 'Rejected')", name="ck_milestones_status"),
		{"schema": "core"},
	)

	scholar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.scholars.id"), nullable=False)
	milestone_type: Mapped[str] = mapped_column(Text, nullable=False)
	status: Mapped[str] = mapped_column(Text, nullable=False, default="Pending")
	approval_body: Mapped[str | None] = mapped_column(Text)
	resolution_number: Mapped[str | None] = mapped_column(Text)
	resolution_date: Mapped[date | None] = mapped_column(Date)
	notes: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
	"""One table = the whole compliance trail: full prev/new snapshots per change, states per transition."""

	__tablename__ = "audit_log"
	__table_args__ = (
		CheckConstraint(
			"action IN ('insert', 'update', 'soft_delete', 'restore', 'transition')",
			name="ck_audit_action",
		),
		{"schema": "core"},
	)

	id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
	table_name: Mapped[str] = mapped_column(Text, nullable=False)
	record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
	action: Mapped[str] = mapped_column(Text, nullable=False)
	from_state: Mapped[str | None] = mapped_column(Text)
	to_state: Mapped[str | None] = mapped_column(Text)
	prev: Mapped[dict | None] = mapped_column(JSONB)
	data: Mapped[dict | None] = mapped_column(JSONB)
	actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("core.users.id"))
	actor_role: Mapped[str] = mapped_column(Text, nullable=False)
	at: Mapped[datetime] = mapped_column(server_default=func.now())


class RefreshToken(Base):
	__tablename__ = "refresh_tokens"
	__table_args__ = ({"schema": "core"},)

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
	)
	user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id"), nullable=False)
	# sha256 of the raw token; never store the raw
	token_hash: Mapped[str] = mapped_column(Text, nullable=False)
	expires_at: Mapped[datetime] = mapped_column(nullable=False)
	revoked_at: Mapped[datetime | None] = mapped_column(default=None)