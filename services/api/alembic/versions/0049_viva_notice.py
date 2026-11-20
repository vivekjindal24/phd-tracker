"""the viva's notice: the Exam Office may sign notices; who signs a department's viva notices,
and the department admin's changes per viva (PRD F17b)

Revision ID: 0049
Revises: 0048
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "'drc_secretary', 'admin', 'drc_chair', 'unit_head', 'dean'"
AFTER = "'exam_office', " + BEFORE


def _check(column: str, signers: str) -> None:
    op.create_check_constraint(
        f"ck_org_units_{column}", "org_units", f"{column} <@ ARRAY[{signers}]::text[]", schema="core"
    )


def upgrade() -> None:
    op.drop_constraint("ck_org_units_notice_signers", "org_units", schema="core", type_="check")
    _check("notice_signers", AFTER)
    op.add_column("org_units", sa.Column("viva_notice_signers", ARRAY(sa.Text())), schema="core")
    _check("viva_notice_signers", AFTER)
    op.add_column("viva_arrangements", sa.Column("notice", JSONB()), schema="core")


def downgrade() -> None:
    op.drop_column("viva_arrangements", "notice", schema="core")
    op.drop_constraint(
        "ck_org_units_viva_notice_signers", "org_units", schema="core", type_="check"
    )
    op.drop_column("org_units", "viva_notice_signers", schema="core")
    op.execute(
        "UPDATE core.org_units SET notice_signers = NULLIF("
        "array_remove(notice_signers, 'exam_office'), '{}') WHERE 'exam_office' = ANY(notice_signers)"
    )
    op.execute(
        "UPDATE core.seminars SET notice = notice - 'signers' WHERE notice->'signers' ? 'exam_office'"
    )
    op.drop_constraint("ck_org_units_notice_signers", "org_units", schema="core", type_="check")
    _check("notice_signers", BEFORE)
