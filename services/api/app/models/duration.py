"""Time records against the UGC maximum duration (DATABASE.md §3.3c, PRD Phase 4)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import TIME_KINDS, sql_in
from app.models.base import Base, DomainRow


class TimeAdjustment(DomainRow, Base):
    """An approved extension / relaxation, or a period of leave, for one scholar."""

    __tablename__ = "time_adjustments"
    __table_args__ = (
        CheckConstraint(f"kind IN ({sql_in(TIME_KINDS)})", name="ck_time_adjustments_kind"),
        CheckConstraint("end_date >= start_date", name="ck_time_adjustments_dates"),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    kind: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    resolution_number: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1
