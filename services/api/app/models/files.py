"""File metadata (DATABASE.md §3.7). Bytes live in object storage, never in Postgres."""

import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import FILE_OWNER_TABLES, FILE_STATUSES, sql_in
from app.models.base import Base, DomainRow


class FileRow(DomainRow, Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(f"table_name IN ({sql_in(FILE_OWNER_TABLES)})", name="ck_files_owner"),
        CheckConstraint(f"status IN ({sql_in(FILE_STATUSES)})", name="ck_files_status"),
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
