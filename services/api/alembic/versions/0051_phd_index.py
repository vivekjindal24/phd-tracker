"""the university's own index of the PhD file: its rows and what fills each (PRD F17)

Revision ID: 0051
Revises: 0050
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("phd_index", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema="core",
    )
    op.create_check_constraint(
        "ck_settings_phd_index", "settings", "jsonb_typeof(phd_index) = 'array'", schema="core"
    )


def downgrade() -> None:
    op.drop_constraint("ck_settings_phd_index", "settings", schema="core", type_="check")
    op.drop_column("settings", "phd_index", schema="core")
