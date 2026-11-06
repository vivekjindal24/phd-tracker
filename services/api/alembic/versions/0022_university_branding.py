"""university branding

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("university_address", sa.Text(), server_default=sa.text("''"), nullable=False),
        schema="core",
    )
    op.create_table(
        "university_logos",
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("university_logos", schema="core")
    op.drop_column("settings", "university_address", schema="core")
