"""who signs a notice in a role several people hold: per department, and the Controller of
Examinations once for the whole university (PRD F17b)

Revision ID: 0052
Revises: 0051
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "org_units",
        sa.Column("notice_names", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="core",
    )
    op.create_check_constraint(
        "ck_org_units_notice_names",
        "org_units",
        "jsonb_typeof(notice_names) = 'object'",
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column("exam_controller_id", UUID(as_uuid=True), sa.ForeignKey("core.users.id")),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("settings", "exam_controller_id", schema="core")
    op.drop_constraint("ck_org_units_notice_names", "org_units", schema="core", type_="check")
    op.drop_column("org_units", "notice_names", schema="core")
