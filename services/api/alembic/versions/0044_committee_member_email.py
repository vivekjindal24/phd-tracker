"""an outside committee member's email, to reach them (PRD F9b)

Revision ID: 0044
Revises: 0043
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "committee_members", sa.Column("email", postgresql.CITEXT()), schema="core"
    )


def downgrade() -> None:
    op.drop_column("committee_members", "email", schema="core")
