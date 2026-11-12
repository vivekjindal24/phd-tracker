"""scholar profile: study mode, gender, category, disability

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKS = {
    "study_mode": "study_mode IN ('full_time', 'part_time')",
    "gender": "gender IN ('female', 'male', 'transgender')",
    "category": "category IN ('general', 'obc', 'sc', 'st', 'ews')",
}


def upgrade() -> None:
    for column in CHECKS:
        op.add_column("scholars", sa.Column(column, sa.Text()), schema="core")
    op.add_column("scholars", sa.Column("has_disability", sa.Boolean()), schema="core")
    for column, check in CHECKS.items():
        op.create_check_constraint(f"ck_scholars_{column}", "scholars", check, schema="core")


def downgrade() -> None:
    for column in (*CHECKS, "has_disability"):
        op.drop_column("scholars", column, schema="core")  # its CHECK goes with the column
