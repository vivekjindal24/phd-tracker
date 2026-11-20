"""who signs a seminar's notice: per department, and the admin's changes per seminar (PRD F17b)

Revision ID: 0048
Revises: 0047
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNERS = "'drc_secretary', 'admin', 'drc_chair', 'unit_head', 'dean'"


def upgrade() -> None:
    op.add_column("org_units", sa.Column("notice_signers", ARRAY(sa.Text())), schema="core")
    op.create_check_constraint(
        "ck_org_units_notice_signers",
        "org_units",
        f"notice_signers <@ ARRAY[{SIGNERS}]::text[]",
        schema="core",
    )
    op.add_column("seminars", sa.Column("notice", JSONB()), schema="core")


def downgrade() -> None:
    op.drop_column("seminars", "notice", schema="core")
    op.drop_constraint("ck_org_units_notice_signers", "org_units", schema="core", type_="check")
    op.drop_column("org_units", "notice_signers", schema="core")
