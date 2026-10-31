"""Documents & thesis module (DATABASE.md §3.4-3.5). The thesis submission is approvable (state
only via app/workflow.py); what happens after its approval — examiner reports, viva,
Shodhganga deposit — lives in its own rows, because an approved item is immutable."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import DOC_KINDS, RECOMMENDATIONS, VIVA_OUTCOMES, sql_in
from app.models.base import Base, DomainRow
from app.models.workflow import ApprovalColumns, approval_constraints

LIVE = text("deleted_at IS NULL")


class Document(DomainRow, Base):
    """A draft, chapter, proposal… Visible only to the scholar and their supervisor(s)."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"doc_kind IN ({sql_in(DOC_KINDS)})", name="ck_documents_kind"),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    doc_kind: Mapped[str] = mapped_column(Text)


class DocumentVersion(DomainRow, Base):
    """Append-only: a version is a file plus a note, numbered per document."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_document_version_no"),
        UniqueConstraint("file_id", name="uq_document_version_file"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"))
    note: Mapped[str] = mapped_column(Text, server_default=text("''"))


class ThesisSubmission(ApprovalColumns, DomainRow, Base):
    """The final thesis; its files are the record's attachments. Plagiarism fields belong to
    the Library step, `examiners` to the Exam Office step (workflow.assert_step_field)."""

    __tablename__ = "thesis_submissions"
    __table_args__ = (
        *approval_constraints("thesis_submissions"),
        CheckConstraint(
            "plagiarism_score IS NULL OR plagiarism_score BETWEEN 0 AND 100",
            name="ck_thesis_plagiarism_score",
        ),
        Index("uq_thesis_active", "scholar_id", unique=True, postgresql_where=LIVE),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    plagiarism_tool: Mapped[str | None] = mapped_column(Text)
    plagiarism_score: Mapped[float | None] = mapped_column(Numeric(5, 2, asdecimal=False))
    examiners: Mapped[str | None] = mapped_column(Text)  # confidential: see thesis.py


class ExaminerReport(DomainRow, Base):
    __tablename__ = "examiner_reports"
    __table_args__ = (
        CheckConstraint(
            f"recommendation IN ({sql_in(RECOMMENDATIONS)})", name="ck_examiner_reports_rec"
        ),
    )

    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("thesis_submissions.id"), index=True
    )
    examiner_name: Mapped[str] = mapped_column(Text)  # confidential until the viva
    institution: Mapped[str] = mapped_column(Text, server_default=text("''"))
    received_on: Mapped[date] = mapped_column(Date)
    recommendation: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Viva(DomainRow, Base):
    __tablename__ = "vivas"
    __table_args__ = (
        CheckConstraint(f"outcome IN ({sql_in(VIVA_OUTCOMES)})", name="ck_vivas_outcome"),
    )

    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("thesis_submissions.id"), index=True
    )
    held_on: Mapped[date] = mapped_column(Date)
    venue: Mapped[str] = mapped_column(Text, server_default=text("''"))
    panel: Mapped[str] = mapped_column(Text, server_default=text("''"))
    outcome: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"))


class ShodhgangaDeposit(DomainRow, Base):
    __tablename__ = "shodhganga_deposits"
    __table_args__ = (
        Index("uq_shodhganga_thesis", "thesis_id", unique=True, postgresql_where=LIVE),
    )

    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("thesis_submissions.id")
    )
    deposited_on: Mapped[date] = mapped_column(Date)
    handle_url: Mapped[str] = mapped_column(Text)


class NoDuesClearance(ApprovalColumns, DomainRow, Base):
    """No dues to the lab, department, library and accounts (PRD M3). Each step's approval is
    that office's confirmation; a thesis waits for it while `require_no_dues` is on."""

    __tablename__ = "no_dues_clearances"
    __table_args__ = (
        *approval_constraints("no_dues_clearances"),
        Index("uq_no_dues_active", "scholar_id", unique=True, postgresql_where=LIVE),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
