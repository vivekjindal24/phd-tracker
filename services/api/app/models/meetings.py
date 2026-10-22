"""Meeting records (DATABASE.md §3.3). Redaction for unshared viewers happens in the API."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import MEETING_SHARES, sql_in
from app.models.base import Base, DomainRow


class Meeting(DomainRow, Base):
    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint(
            f"shared_with <@ ARRAY[{sql_in(MEETING_SHARES)}]::text[]",
            name="ck_meetings_shared_with",
        ),
        CheckConstraint(
            "next_meeting_date IS NULL OR next_meeting_date >= meeting_date",
            name="ck_meetings_next_date",
        ),
        Index(
            "ix_meetings_agenda_trgm",
            "agenda",
            postgresql_using="gin",
            postgresql_ops={"agenda": "gin_trgm_ops"},
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    supervisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("faculty.id"), index=True
    )
    meeting_date: Mapped[date] = mapped_column(Date)
    agenda: Mapped[str] = mapped_column(Text)
    minutes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    action_items: Mapped[str] = mapped_column(Text, server_default=text("''"))
    next_meeting_date: Mapped[date | None] = mapped_column(Date)
    shared_with: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
