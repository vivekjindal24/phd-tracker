"""AISHE's research-degree fields: a scholar's minority community and nationality (with the
country for a scholar from abroad), and each unit's AISHE discipline (returns.py)

Revision ID: 0063
Revises: 0062
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("minority", "nationality", "country"):
        op.add_column("scholars", sa.Column(column, sa.Text()), schema="core")
    op.create_check_constraint(
        "ck_scholars_minority",
        "scholars",
        "minority IN ('none', 'muslim', 'christian', 'sikh', 'buddhist', 'jain', 'parsi')",
        schema="core",
    )
    op.create_check_constraint(
        "ck_scholars_nationality",
        "scholars",
        "nationality IN ('indian', 'nri', 'pio', 'foreign')",
        schema="core",
    )
    op.create_check_constraint(
        "ck_scholars_country",
        "scholars",
        "(country IS NULL) = (nationality IS NULL OR nationality = 'indian')"
        " AND (country IS NULL OR char_length(country) BETWEEN 1 AND 100)",
        schema="core",
    )
    op.add_column("org_units", sa.Column("aishe_discipline", sa.Text()), schema="core")
    op.create_check_constraint(
        "ck_org_units_aishe_discipline",
        "org_units",
        "aishe_discipline IS NULL OR char_length(aishe_discipline) BETWEEN 1 AND 200",
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("org_units", "aishe_discipline", schema="core")
    for column in ("country", "nationality", "minority"):
        op.drop_column("scholars", column, schema="core")
