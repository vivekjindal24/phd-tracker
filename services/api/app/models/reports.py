"""Six-monthly progress reports (DATABASE.md §3.4). State changes only via app/workflow.py."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import PERIODS, sql_in
from app.models.base import Base, DomainRow
from app.models.workflow import ApprovalColumns, approval_constraints


class ProgressReport(ApprovalColumns, DomainRow, Base):
    __tablename__ = "progress_reports"
    __table_args__ = (
        *approval_constraints("progress_reports"),
        CheckConstraint("report_year BETWEEN 2000 AND 2100", name="ck_apr_year"),
        CheckConstraint(f"period IN ({sql_in(PERIODS)})", name="ck_apr_period"),
        Index(
            "uq_apr_active",
            "scholar_id",
            "report_year",
            "period",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_progress_reports_summary_trgm",
            "summary",
            postgresql_using="gin",
            postgresql_ops={"summary": "gin_trgm_ops"},
        ),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    report_year: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
