"""how the university writes a date, on every screen, PDF, notice and email

Revision ID: 0053
Revises: 0052
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORMATS = (
    "'d_mon_yyyy', 'd_month_yyyy', 'dd/mm/yyyy', 'dd-mm-yyyy', 'dd.mm.yyyy', 'yyyy-mm-dd', "
    "'mm/dd/yyyy'"
)


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("date_format", sa.Text(), nullable=False, server_default="d_mon_yyyy"),
        schema="core",
    )
    op.create_check_constraint(
        "ck_settings_date_format", "settings", f"date_format IN ({FORMATS})", schema="core"
    )


def downgrade() -> None:
    op.drop_constraint("ck_settings_date_format", "settings", schema="core", type_="check")
    op.drop_column("settings", "date_format", schema="core")
