"""A scholar's grievance (grievances.py; UGC Redressal of Grievances of Students Regulations,
2023). Not an approvable item: a case with its own lifecycle in `status`, changed only by
grievances.py. Read by the scholar, the grievance cell and the Vice Chancellor; by the
Ombudsperson once appealed; never by the supervisor, heads or other offices."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import GRIEVANCE_CATEGORIES, GRIEVANCE_STATUSES, sql_in
from app.models.base import Base, DomainRow


class Grievance(DomainRow, Base):
    __tablename__ = "grievances"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({sql_in(GRIEVANCE_CATEGORIES)})", name="ck_grievances_category"
        ),
        CheckConstraint(f"status IN ({sql_in(GRIEVANCE_STATUSES)})", name="ck_grievances_status"),
        CheckConstraint("char_length(subject) BETWEEN 1 AND 200", name="ck_grievances_subject"),
        CheckConstraint(
            "char_length(description) BETWEEN 1 AND 5000", name="ck_grievances_description"
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    category: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    due_on: Mapped[date] = mapped_column(Date)  # the cell's, then the appeal's, deadline
    decision: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    appeal_reason: Mapped[str | None] = mapped_column(Text)
    appealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appeal_decision: Mapped[str | None] = mapped_column(Text)
    appeal_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appeal_decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
