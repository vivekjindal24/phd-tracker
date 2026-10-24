"""Research record modules: publications (approvable) and conferences (DATABASE.md §3.4-3.5).
Publication state changes only via app/workflow.py; `pub_status` is bibliographic, not state."""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.enums import CONFERENCE_TYPES, INDEXINGS, PUB_STATUSES, PUB_TYPES, sql_in
from app.models.base import Base, DomainRow
from app.models.workflow import ApprovalColumns, approval_constraints


def _trgm(name: str, column: str) -> Index:
    return Index(name, column, postgresql_using="gin", postgresql_ops={column: "gin_trgm_ops"})


class Publication(ApprovalColumns, DomainRow, Base):
    __tablename__ = "publications"
    __table_args__ = (
        *approval_constraints("publications"),
        CheckConstraint(f"pub_type IN ({sql_in(PUB_TYPES)})", name="ck_publications_type"),
        CheckConstraint(f"pub_status IN ({sql_in(PUB_STATUSES)})", name="ck_publications_status"),
        CheckConstraint(
            f"indexing <@ ARRAY[{sql_in(INDEXINGS)}]::text[]", name="ck_publications_indexing"
        ),
        CheckConstraint("pub_year BETWEEN 1950 AND 2100", name="ck_publications_year"),
        _trgm("ix_publications_title_trgm", "title"),
        _trgm("ix_publications_venue_trgm", "venue"),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    pub_type: Mapped[str] = mapped_column(Text)
    venue: Mapped[str] = mapped_column(Text)
    issn_isbn: Mapped[str | None] = mapped_column(Text)
    indexing: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    doi: Mapped[str | None] = mapped_column(Text)
    pub_year: Mapped[int] = mapped_column(Integer)
    pub_status: Mapped[str] = mapped_column(Text)


class Conference(DomainRow, Base):
    __tablename__ = "conferences"
    __table_args__ = (
        CheckConstraint(f"event_type IN ({sql_in(CONFERENCE_TYPES)})", name="ck_conferences_type"),
    )

    scholar_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scholars.id"), index=True
    )
    event_name: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date)
    place: Mapped[str] = mapped_column(Text, server_default=text("''"))
    title: Mapped[str | None] = mapped_column(Text)
