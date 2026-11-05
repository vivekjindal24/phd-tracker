"""cross-unit directory switch on org units

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "org_units",
        sa.Column(
            "cross_unit_directory", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("org_units", "cross_unit_directory", schema="core")
