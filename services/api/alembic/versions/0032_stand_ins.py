"""supervisor stand-ins and on-behalf approvals

Revision ID: 0032
Revises: 0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "supervisor_stand_ins",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("faculty_id", UUID, sa.ForeignKey("core.faculty.id"), nullable=False),
        sa.Column("stand_in_id", UUID, sa.ForeignKey("core.faculty.id"), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("stand_in_id <> faculty_id", name="ck_stand_ins_not_self"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_stand_ins_dates"),
        schema="core",
    )
    op.create_index(
        "uq_stand_ins_faculty",
        "supervisor_stand_ins",
        ["faculty_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_stand_ins_stand_in", "supervisor_stand_ins", ["stand_in_id"], schema="core"
    )
    op.add_column(
        "approval_actions",
        sa.Column("on_behalf_of", UUID, sa.ForeignKey("core.users.id")),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("approval_actions", "on_behalf_of", schema="core")
    op.drop_table("supervisor_stand_ins", schema="core")
