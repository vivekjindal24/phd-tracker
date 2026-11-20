"""the PhD file's forms as the university names them: title, form number, copy list (PRD F17)

Revision ID: 0050
Revises: 0049
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("phd_forms", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="core",
    )
    op.create_check_constraint(
        "ck_settings_phd_forms", "settings", "jsonb_typeof(phd_forms) = 'object'", schema="core"
    )


def downgrade() -> None:
    op.drop_constraint("ck_settings_phd_forms", "settings", schema="core", type_="check")
    op.drop_column("settings", "phd_forms", schema="core")
