"""a university switch: the paper itself must be attached to a publication

Revision ID: 0061
Revises: 0060
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "publication_file_required", sa.Boolean(), nullable=False, server_default="false"
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("settings", "publication_file_required", schema="core")
