"""The RDC / committee register (DATABASE.md §3.3)."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import APPROVAL_BODIES, MILESTONE_STATUSES, MILESTONE_TYPES, sql_in
from app.models.base import Base, DomainRow


class Milestone(DomainRow, Base):
    __tablename__ = "milestones"
    __table_args__ = (
        CheckConstraint(
            f"milestone_type IN ({sql_in(MILESTONE_TYPES)})", name="ck_milestones_type"
        ),
        CheckConstraint(f"status IN ({sql_in(MILESTONE_STATUSES)})", name="ck_milestones_status"),
        CheckConstraint(f"approval_body IN ({sql_in(APPROVAL_BODIES)})", name="ck_milestones_body"),
        Index(
            "ix_milestones_resolution_trgm",
            "resolution_number",
            postgresql_using="gin",
            postgresql_ops={"resolution_number": "gin_trgm_ops"},
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    milestone_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'Pending'"))
    approval_body: Mapped[str] = mapped_column(Text)
    resolution_number: Mapped[str | None] = mapped_column(Text)
    resolution_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
