"""two-factor login: per-user authenticator secret and the university switch

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret", sa.Text()), schema="core")
    op.add_column(
        "users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True)), schema="core"
    )
    op.add_column("users", sa.Column("totp_last_step", sa.BigInteger()), schema="core")
    op.add_column(
        "users",
        sa.Column(
            "recovery_hashes",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column(
            "require_two_factor", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("settings", "require_two_factor", schema="core")
    for column in ("recovery_hashes", "totp_last_step", "totp_enabled_at", "totp_secret"):
        op.drop_column("users", column, schema="core")
