"""Flat comment threads on records (DATABASE.md §3.7). No FK on record_id (polymorphic);
the CHECK whitelist stands in for it."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import COMMENT_TARGETS, sql_in
from app.models.base import Base, DomainRow


class Comment(DomainRow, Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint(f"table_name IN ({sql_in(COMMENT_TARGETS)})", name="ck_comments_target"),
        CheckConstraint("char_length(body) BETWEEN 1 AND 4000", name="ck_comments_body"),
        Index("ix_comments_record", "table_name", "record_id"),
    )

    table_name: Mapped[str] = mapped_column(Text)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
