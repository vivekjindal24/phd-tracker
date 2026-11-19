"""a register entry remembers the seminar whose recommendation opened it (PRD F15 / F9)

Revision ID: 0043
Revises: 0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column("seminar_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.seminars.id")),
        schema="core",
    )
    op.create_index(
        "uq_milestone_seminar",
        "milestones",
        ["scholar_id", "seminar_id"],
        unique=True,
        postgresql_where=sa.text("seminar_id IS NOT NULL AND deleted_at IS NULL"),
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("uq_milestone_seminar", "milestones", schema="core")
    op.drop_column("milestones", "seminar_id", schema="core")
