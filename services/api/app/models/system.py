"""Cross-cutting tables: audit log, refresh tokens, notifications, job runs (DATABASE.md §3.7)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import AUDIT_ACTIONS, EMAIL_STATUSES, NOTIFICATION_CATEGORIES, sql_in
from app.models.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(f"action IN ({sql_in(AUDIT_ACTIONS)})", name="ck_audit_action"),
        Index("ix_audit_record", "table_name", "record_id"),
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
            f"email_status IN ({sql_in(EMAIL_STATUSES)})", name="ck_notifications_email_status"
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("job_name", "run_date", name="uq_job_runs"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_name: Mapped[str] = mapped_column(Text)
    run_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
