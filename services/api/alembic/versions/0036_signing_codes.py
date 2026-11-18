"""signing: the require_signing setting and emailed signing codes

Revision ID: 0036
Revises: 0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
ITEMS = (
    "'progress_report', 'publication', 'coursework_clearance', 'thesis_submission', "
    "'no_dues_clearance', 'fellowship_claim'"
)


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("require_signing", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="core",
    )
    op.create_table(
        "signing_codes",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID, sa.ForeignKey("core.users.id"), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("item_id", UUID, nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(f"item_type IN ({ITEMS})", name="ck_signing_codes_item"),
        sa.CheckConstraint("action IN ('approve', 'send_back')", name="ck_signing_codes_action"),
        schema="core",
    )
    op.create_index(
        "ix_signing_codes_user", "signing_codes", ["user_id", "created_at"], schema="core"
    )


def downgrade() -> None:
    op.drop_table("signing_codes", schema="core")
    op.drop_column("settings", "require_signing", schema="core")
