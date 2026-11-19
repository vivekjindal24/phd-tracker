"""File metadata (DATABASE.md §3.7). Bytes live in object storage, never in Postgres."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import (
    DOCUMENT_KINDS,
    FILE_OWNER_TABLES,
    FILE_SLOTS,
    FILE_STATUSES,
    PHD_ANNEXURES,
    sql_in,
)
from app.models.base import Base, DomainRow

LIVE = text("deleted_at IS NULL")


class FileRow(DomainRow, Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(f"table_name IN ({sql_in(FILE_OWNER_TABLES)})", name="ck_files_owner"),
        CheckConstraint(f"status IN ({sql_in(FILE_STATUSES)})", name="ck_files_status"),
        CheckConstraint(
            f"slot IS NULL OR (table_name = 'scholars' AND slot IN ({sql_in(FILE_SLOTS)}))",
            name="ck_files_slot",
        ),
        CheckConstraint("size_bytes > 0", name="ck_files_size"),
        Index("uq_files_storage_key", "storage_key", unique=True),
        Index("ix_files_owner", "table_name", "record_id"),
    )

    storage_key: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    etag: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    table_name: Mapped[str] = mapped_column(Text)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # A named place on a scholar's record (employer NOC, entrance minutes); null = loose file.
    slot: Mapped[str | None] = mapped_column(Text)


class SignedCopy(DomainRow, Base):
    """The scan of a paper signed by hand, standing for one entry of the PhD file (PRD F17b): its
    annexure, the record behind the entry and which of its papers it is. The scan is a file on
    this row. Counts once approved by an admin over the scholar's unit or the Research Office
    (the Exam Office too, for the examiners' papers); their own uploads are approved as they
    upload. The newest copy of each paper with its scan in place is the one in use."""

    __tablename__ = "signed_copies"
    __table_args__ = (
        CheckConstraint(f"annexure IN ({sql_in(PHD_ANNEXURES)})", name="ck_signed_copies_annexure"),
        CheckConstraint(
            "(approved_by IS NULL) = (approved_at IS NULL)", name="ck_signed_copies_approved"
        ),
        CheckConstraint(f"kind IN ({sql_in(tuple(DOCUMENT_KINDS))})", name="ck_signed_copies_kind"),
        Index("ix_signed_copies_scholar", "scholar_id", postgresql_where=LIVE),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scholars.id"))
    annexure: Mapped[str] = mapped_column(Text)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Which of the entry's papers (enums.DOCUMENT_KINDS): a seminar's notification, report, …
    kind: Mapped[str] = mapped_column(Text, server_default=text("'signed_copy'"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
