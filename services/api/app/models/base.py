import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

SCHEMA = "core"


class Ltree(UserDefinedType):
    """Postgres ltree; bound and returned as a dotted string."""

    cache_ok = True

    def get_col_spec(self, **_: object) -> str:
        return "LTREE"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DomainRow(Timestamps):
    """Every domain row: uuid id, timestamps, soft-delete marker."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
