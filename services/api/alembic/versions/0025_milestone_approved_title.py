"""milestone approved title

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("milestones", sa.Column("approved_title", sa.Text()), schema="core")


def downgrade() -> None:
    op.drop_column("milestones", "approved_title", schema="core")
