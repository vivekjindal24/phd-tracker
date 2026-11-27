"""Organisation tree and people (DATABASE.md §3.1)."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    ASSIGNED_ROLES,
    CATEGORIES,
    DESIGNATIONS,
    GENDERS,
    GRIEVANCE_ROLES,
    LEFT_REASONS,
    MINORITIES,
    NATIONALITIES,
    NOTICE_SIGNERS,
    NOTIFICATION_CATEGORIES,
    OFFICE_ROLES,
    STAGES,
    STUDY_MODES,
    SUPERVISION_ROLES,
    UNIT_ROLES,
    WHATSAPP_NUMBER_RE,
    sql_in,
)
from app.models.base import Base, DomainRow, Ltree
from app.models.workflow import ApprovalColumns, approval_constraints

LIVE = text("deleted_at IS NULL")


class OrgUnit(DomainRow, Base):
    __tablename__ = "org_units"
    __table_args__ = (
        Index(
            "uq_org_root",
            text("(parent_id IS NULL)"),
            unique=True,
            postgresql_where=text("parent_id IS NULL AND deleted_at IS NULL"),
        ),
        Index("uq_org_units_code", "code", unique=True, postgresql_where=LIVE),
        Index("uq_org_units_path", "path", unique=True, postgresql_where=LIVE),
        Index("ix_org_units_path_gist", "path", postgresql_using="gist"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="ck_org_units_name"),
        CheckConstraint(
            f"notice_signers <@ ARRAY[{sql_in(NOTICE_SIGNERS)}]::text[]",
            name="ck_org_units_notice_signers",
        ),
        CheckConstraint(
            f"viva_notice_signers <@ ARRAY[{sql_in(NOTICE_SIGNERS)}]::text[]",
            name="ck_org_units_viva_notice_signers",
        ),
        CheckConstraint("jsonb_typeof(notice_names) = 'object'", name="ck_org_units_notice_names"),
        CheckConstraint(
            "aishe_discipline IS NULL OR char_length(aishe_discipline) BETWEEN 1 AND 200",
            name="ck_org_units_aishe_discipline",
        ),
        Index(
            "ix_org_units_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    code: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Ltree)
    cross_unit_directory: Mapped[bool] = mapped_column(Boolean, server_default=false())
    aishe_discipline: Mapped[str | None] = mapped_column(Text)  # as AISHE names it (returns.py)
    # Who signs the unit's seminar notices, in order (enums.NOTICE_SIGNERS); null: the default.
    notice_signers: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    viva_notice_signers: Mapped[list[str] | None] = mapped_column(ARRAY(Text))  # likewise, vivas
    # Who signs a notice in a role several people hold: {signer key: user id} (notices.py).
    notice_names: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class User(DomainRow, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_email", "email", unique=True, postgresql_where=LIVE),
        CheckConstraint(
            f"email_muted <@ ARRAY[{sql_in(NOTIFICATION_CATEGORIES)}]::text[]",
            name="ck_users_email_muted",
        ),
        CheckConstraint(
            f"whatsapp_muted <@ ARRAY[{sql_in(NOTIFICATION_CATEGORIES)}]::text[]",
            name="ck_users_whatsapp_muted",
        ),
        CheckConstraint(
            f"whatsapp_number ~ '{WHATSAPP_NUMBER_RE}'", name="ck_users_whatsapp_number"
        ),
        Index(
            "ix_users_full_name_trgm",
            "full_name",
            postgresql_using="gin",
            postgresql_ops={"full_name": "gin_trgm_ops"},
        ),
    )

    email: Mapped[str] = mapped_column(CITEXT)
    # NULL until the person sets one (invited users, SSO-only users): password login fails.
    password_hash: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # An external thesis reviewer: reaches only their own reviews (auth/deps.py).
    is_reviewer: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Two-factor login (SECURITY.md §1). ponytail: the secret is stored as it is, protected by
    # the disk encryption SECURITY.md §8 requires; wrap it with a dedicated key if a database
    # dump must not be enough to mint codes.
    totp_secret: Mapped[str | None] = mapped_column(Text)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)  # a code works once
    recovery_hashes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    email_muted: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    # When the person last read the privacy notice; shown again once it changes (privacy.py).
    privacy_notice_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set only by the person themself — setting it is the WhatsApp opt-in (PRD F5).
    whatsapp_number: Mapped[str | None] = mapped_column(Text)
    whatsapp_muted: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None


class Signature(DomainRow, Base):
    """A person's specimen signature (PRD F17b): one live row each. Usable for signing only
    once confirmed by someone else — an admin over the person's unit or the Research Office."""

    __tablename__ = "signatures"
    __table_args__ = (
        Index("uq_signatures_user", "user_id", unique=True, postgresql_where=LIVE),
        CheckConstraint(
            "(confirmed_by IS NULL) = (confirmed_at IS NULL) AND confirmed_by <> user_id",
            name="ck_signatures_confirmed",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScholarPhoto(DomainRow, Base):
    """A scholar's photo (PRD F6), shown on their profile to whoever may open it. One live row
    each; the scholar or an admin over their unit puts it there (photos.py)."""

    __tablename__ = "scholar_photos"
    __table_args__ = (
        Index("uq_scholar_photos_scholar", "scholar_id", unique=True, postgresql_where=LIVE),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scholars.id"))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(Text)


class RoleAssignment(DomainRow, Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        CheckConstraint(f"role IN ({sql_in(ASSIGNED_ROLES)})", name="ck_role_assignments_role"),
        CheckConstraint(
            f"(role IN ({sql_in(UNIT_ROLES)}) AND unit_id IS NOT NULL)"
            f" OR (role IN ({sql_in(OFFICE_ROLES + GRIEVANCE_ROLES)}) AND unit_id IS NULL)",
            name="ck_role_scope",
        ),
        Index(
            "uq_role_assignment_active",
            "user_id",
            "role",
            text("coalesce(unit_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
            postgresql_where=LIVE,
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    role: Mapped[str] = mapped_column(Text)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )


class Faculty(DomainRow, Base):
    __tablename__ = "faculty"
    __table_args__ = (
        Index("uq_faculty_user", "user_id", unique=True, postgresql_where=LIVE),
        CheckConstraint(f"designation IN ({sql_in(DESIGNATIONS)})", name="ck_faculty_designation"),
        CheckConstraint("max_scholars BETWEEN 0 AND 20", name="ck_faculty_max_scholars"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    employee_id: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str] = mapped_column(Text)
    max_scholars: Mapped[int] = mapped_column(Integer)
    can_supervise: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Scholar(DomainRow, Base):
    __tablename__ = "scholars"
    __table_args__ = (
        Index("uq_scholars_user", "user_id", unique=True, postgresql_where=LIVE),
        Index("uq_scholars_roll_number", "roll_number", unique=True, postgresql_where=LIVE),
        CheckConstraint(f"stage IN ({sql_in(STAGES)})", name="ck_scholars_stage"),
        CheckConstraint(
            "co_supervisor_id IS NULL OR co_supervisor_id <> supervisor_id",
            name="ck_scholars_co_supervisor",
        ),
        CheckConstraint(f"study_mode IN ({sql_in(STUDY_MODES)})", name="ck_scholars_study_mode"),
        CheckConstraint(f"gender IN ({sql_in(GENDERS)})", name="ck_scholars_gender"),
        CheckConstraint(f"category IN ({sql_in(CATEGORIES)})", name="ck_scholars_category"),
        CheckConstraint(f"minority IN ({sql_in(MINORITIES)})", name="ck_scholars_minority"),
        CheckConstraint(
            f"nationality IN ({sql_in(NATIONALITIES)})", name="ck_scholars_nationality"
        ),
        CheckConstraint(
            "(country IS NULL) = (nationality IS NULL OR nationality = 'indian')"
            " AND (country IS NULL OR char_length(country) BETWEEN 1 AND 100)",
            name="ck_scholars_country",
        ),
        CheckConstraint(
            f"(left_on IS NULL AND left_reason IS NULL) OR "
            f"(left_on IS NOT NULL AND left_reason IN ({sql_in(LEFT_REASONS)}))",
            name="ck_scholars_left",
        ),
        Index(
            "ix_scholars_roll_number_trgm",
            "roll_number",
            postgresql_using="gin",
            postgresql_ops={"roll_number": "gin_trgm_ops"},
        ),
        Index(
            "ix_scholars_research_title_trgm",
            "research_title",
            postgresql_using="gin",
            postgresql_ops={"research_title": "gin_trgm_ops"},
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id"), index=True
    )
    roll_number: Mapped[str] = mapped_column(Text)
    research_title: Mapped[str | None] = mapped_column(Text)
    admission_date: Mapped[date | None] = mapped_column(Date)
    stage: Mapped[str] = mapped_column(Text, server_default=text("'Registered'"))
    # Profile (PRD F6). NULL = not recorded. Gender, category and disability are personal data:
    # read only through scope.sees_personal.
    study_mode: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    has_disability: Mapped[bool | None] = mapped_column(Boolean)
    minority: Mapped[str | None] = mapped_column(Text)
    nationality: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)  # an NRI's, PIO's or foreigner's
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), index=True
    )
    co_supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), index=True
    )
    # Printed on the university's forms; personal data like gender (scope.sees_personal).
    father_name: Mapped[str | None] = mapped_column(Text)
    # A scholar who withdrew or whose registration was cancelled (drop-outs, Phase 4).
    left_on: Mapped[date | None] = mapped_column(Date)
    left_reason: Mapped[str | None] = mapped_column(Text)


class SupervisorAppointment(DomainRow, Base):
    """One appointment of a supervisor or co-supervisor to a scholar (Form IV), kept for good:
    a change of supervisor ends the current row and opens a new one, so who guided the scholar
    when stays on record. The open row mirrors `scholars.supervisor_id` / `co_supervisor_id`;
    both change only through app/supervision.py."""

    __tablename__ = "supervisor_appointments"
    __table_args__ = (
        CheckConstraint(
            f"role IN ({sql_in(SUPERVISION_ROLES)})", name="ck_supervisor_appointments_role"
        ),
        CheckConstraint(
            "ended_on IS NULL OR appointed_on IS NULL OR ended_on >= appointed_on",
            name="ck_supervisor_appointments_dates",
        ),
        Index(
            "uq_supervisor_appointment_open",
            "scholar_id",
            "role",
            unique=True,
            postgresql_where=text("ended_on IS NULL AND deleted_at IS NULL"),
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("faculty.id"))
    role: Mapped[str] = mapped_column(Text)
    appointed_on: Mapped[date | None] = mapped_column(Date)  # from the order; null = unknown
    order_ref: Mapped[str | None] = mapped_column(Text)
    ended_on: Mapped[date | None] = mapped_column(Date)  # null: the current appointment


class SupervisorChange(ApprovalColumns, DomainRow, Base):
    """A change of a scholar's supervisor, through its approval chain (owner, 2026-11-22): the
    department admin proposes the new supervisor with the reason; on the final approval the
    change happens (supervision.change), with the order reference and date on the new
    appointment. One open change per scholar."""

    __tablename__ = "supervisor_changes"
    __table_args__ = (
        *approval_constraints("supervisor_changes"),
        CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 2000", name="ck_supervisor_changes_reason"
        ),
        Index(
            "uq_supervisor_change_open",
            "scholar_id",
            unique=True,
            postgresql_where=text("state <> 'approved' AND deleted_at IS NULL"),
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    from_faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id")
    )  # the supervisor when it was proposed
    to_faculty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("faculty.id"))
    from_name: Mapped[str | None] = mapped_column(Text)  # names as they were when proposed
    to_name: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    scholar_consent: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    order_ref: Mapped[str | None] = mapped_column(Text)  # the order appointing the new one
    effective_on: Mapped[date | None] = mapped_column(Date)  # the order's date; else approval's
