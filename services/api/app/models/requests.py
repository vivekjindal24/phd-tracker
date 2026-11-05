"""Requests to faculty the requester cannot see (DATABASE.md §3): one seminar or one scholar,
answered by the person asked. Not an approvable item: no chain, one yes or no."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import FACULTY_REQUEST_KINDS, FACULTY_REQUEST_STATUSES, sql_in
from app.models.base import Base, DomainRow


class FacultyRequest(DomainRow, Base):
    __tablename__ = "faculty_requests"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(FACULTY_REQUEST_KINDS)})", name="ck_faculty_req_kind"),
        CheckConstraint(
            f"status IN ({sql_in(FACULTY_REQUEST_STATUSES)})", name="ck_faculty_req_status"
        ),
        CheckConstraint(
            "(kind = 'seminar_panel' AND seminar_id IS NOT NULL AND scholar_id IS NULL)"
            " OR (kind = 'co_supervisor' AND scholar_id IS NOT NULL AND seminar_id IS NULL)",
            name="ck_faculty_req_target",
        ),
        Index("ix_faculty_requests_email", "email"),
    )

    kind: Mapped[str] = mapped_column(Text)
    seminar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seminars.id"), index=True
    )
    scholar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    email: Mapped[str] = mapped_column(CITEXT)
    # NULL when the address matches no faculty; the sender is never told which (SECURITY.md).
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    note: Mapped[str] = mapped_column(Text, server_default=text("''"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
