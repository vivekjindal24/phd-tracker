"""A person's request about their own personal data (DPDP Act 2023): to correct it, erase it, or
anything else. The university's privacy officer answers it (privacy.py)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import DATA_REQUEST_KINDS, DATA_REQUEST_STATUSES, sql_in
from app.models.base import Base, DomainRow


class DataRequest(DomainRow, Base):
    __tablename__ = "data_requests"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(DATA_REQUEST_KINDS)})", name="ck_data_requests_kind"),
        CheckConstraint(
            f"status IN ({sql_in(DATA_REQUEST_STATUSES)})", name="ck_data_requests_status"
        ),
        CheckConstraint("char_length(details) BETWEEN 1 AND 3000", name="ck_data_requests_details"),
        CheckConstraint(
            "(status = 'open' AND reply IS NULL AND answered_at IS NULL AND answered_by IS NULL)"
            " OR (status = 'answered' AND char_length(reply) BETWEEN 1 AND 3000"
            " AND answered_at IS NOT NULL AND answered_by IS NOT NULL)",
            name="ck_data_requests_answer",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    kind: Mapped[str] = mapped_column(Text)
    details: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    reply: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
