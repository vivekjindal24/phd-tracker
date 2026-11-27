"""Cross-cutting tables: audit log, refresh tokens, notifications, job runs (DATABASE.md §3.7)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    FetchedValue,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    AUDIT_ACTIONS,
    DELIVERY_STATUSES,
    ITEM_TYPES,
    NOTIFICATION_CATEGORIES,
    PASSWORD_TOKEN_PURPOSES,
    SIGNING_ACTIONS,
    SSO_PROVIDERS,
    sql_in,
)
from app.models.base import Base, DomainRow


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(f"action IN ({sql_in(AUDIT_ACTIONS)})", name="ck_audit_action"),
        Index("ix_audit_record", "table_name", "record_id"),
        UniqueConstraint("seq", name="uq_audit_log_seq"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    table_name: Mapped[str] = mapped_column(Text)
    record_id: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    from_state: Mapped[str | None] = mapped_column(Text)
    to_state: Mapped[str | None] = mapped_column(Text)
    prev: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set by the database on insert (trigger audit_chain, migration 0068): the entry's place in
    # the chain, and its seal over its contents and the previous entry's seal.
    seq: Mapped[int] = mapped_column(BigInteger, server_default=FetchedValue())
    hash: Mapped[str] = mapped_column(Text, server_default=FetchedValue())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordToken(Base):
    """Single-use set-password links (invite / forgot password). Only the sha256 is stored."""

    __tablename__ = "password_tokens"
    __table_args__ = (
        CheckConstraint(
            f"purpose IN ({sql_in(PASSWORD_TOKEN_PURPOSES)})", name="ck_password_tokens_purpose"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    purpose: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SigningCode(Base):
    """An emailed code that signs one action on one item (PRD F17b): six digits, ten minutes,
    used once, five wrong tries end it. Only the sha256 is stored."""

    __tablename__ = "signing_codes"
    __table_args__ = (
        CheckConstraint(f"item_type IN ({sql_in(ITEM_TYPES)})", name="ck_signing_codes_item"),
        CheckConstraint(f"action IN ({sql_in(SIGNING_ACTIONS)})", name="ck_signing_codes_action"),
        Index("ix_signing_codes_user", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    item_type: Mapped[str] = mapped_column(Text)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(Text)
    code_hash: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SsoState(Base):
    """One single sign-on attempt: the OIDC state/nonce/PKCE verifier while the user is at the
    provider, then the single-use code the browser trades for tokens (SECURITY.md §1)."""

    __tablename__ = "sso_states"
    __table_args__ = (
        CheckConstraint(f"provider IN ({sql_in(SSO_PROVIDERS)})", name="ck_sso_states_provider"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(Text)
    state_hash: Mapped[str] = mapped_column(Text, unique=True)
    nonce: Mapped[str] = mapped_column(Text)
    code_verifier: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    callback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    exchange_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    exchanged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginAttempt(Base):
    """Failed logins, for throttling (SECURITY.md §1). Rows older than the window are inert."""

    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_email_at", "email", "at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({sql_in(NOTIFICATION_CATEGORIES)})", name="ck_notifications_category"
        ),
        CheckConstraint(
            f"email_status IN ({sql_in(DELIVERY_STATUSES)})", name="ck_notifications_email_status"
        ),
        CheckConstraint(
            f"whatsapp_status IN ({sql_in(DELIVERY_STATUSES)})",
            name="ck_notifications_whatsapp_status",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    category: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, server_default=text("''"))
    link: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_status: Mapped[str] = mapped_column(Text, server_default=text("'not_sent'"))
    email_error: Mapped[str | None] = mapped_column(Text)
    whatsapp_status: Mapped[str] = mapped_column(Text, server_default=text("'not_sent'"))
    whatsapp_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("job_name", "run_date", name="uq_job_runs"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_name: Mapped[str] = mapped_column(Text)
    run_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Announcement(DomainRow, Base):
    """A notice on the notice board: for the whole university (no unit) or for one department
    and everything below it, posted by the Research Office, the root admin or the unit's admin
    (announcements.py). Its file, if any, hangs off it in files (owner `announcements`)."""

    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="ck_announcements_title"),
        CheckConstraint("char_length(body) <= 5000", name="ck_announcements_body"),
        Index("ix_announcements_unit_id", "unit_id"),
    )

    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("org_units.id")
    )
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, server_default=text("''"))
    pinned: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    ends_on: Mapped[date | None] = mapped_column(Date)  # off the board after this day
    posted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
