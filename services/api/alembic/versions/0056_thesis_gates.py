"""thesis submission gates: minimum duration, plagiarism limit, publications

Revision ID: 0056
Revises: 0055
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    sa.Column("min_duration_years", sa.Integer(), nullable=False, server_default="3"),
    sa.Column(
        "max_plagiarism_percent", sa.Numeric(5, 2), nullable=False, server_default="10"
    ),
    sa.Column("min_publications", sa.Integer(), nullable=False, server_default="0"),
    sa.Column(
        "publications_indexed_only", sa.Boolean(), nullable=False, server_default="false"
    ),
)


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("settings", column, schema="core")
    op.create_check_constraint(
        "ck_settings_thesis_gates",
        "settings",
        "min_duration_years BETWEEN 0 AND 6 AND min_publications BETWEEN 0 AND 10 "
        "AND max_plagiarism_percent BETWEEN 0 AND 100",
        schema="core",
    )


def downgrade() -> None:
    op.drop_constraint("ck_settings_thesis_gates", "settings", schema="core", type_="check")
    for column in reversed(COLUMNS):
        op.drop_column("settings", column.name, schema="core")
