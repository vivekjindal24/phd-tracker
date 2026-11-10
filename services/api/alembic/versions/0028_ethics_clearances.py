"""research ethics clearances and the thesis gate

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNERS = (
    "'scholars', 'publications', 'conferences', 'documents', 'thesis_submissions', "
    "'examiner_reports', 'vivas', 'shodhganga_deposits', 'utilisation_certificates', "
    "'thesis_reviews'"
)


def _file_owners(owners: str) -> None:
    op.drop_constraint("ck_files_owner", "files", schema="core", type_="check")
    op.create_check_constraint(
        "ck_files_owner", "files", f"table_name IN ({owners})", schema="core"
    )


def upgrade() -> None:
    op.create_table(
        "ethics_clearances",
        sa.Column("scholar_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("committee", sa.Text(), nullable=True),
        sa.Column("approval_number", sa.Text(), nullable=True),
        sa.Column("approved_on", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('human', 'animal', 'biosafety', 'not_required')", name="ck_ethics_kind"
        ),
        sa.CheckConstraint(
            "(kind = 'not_required' AND approval_number IS NULL AND approved_on IS NULL"
            " AND valid_until IS NULL AND notes <> '')"
            " OR (kind <> 'not_required' AND approval_number IS NOT NULL"
            " AND approved_on IS NOT NULL)",
            name="ck_ethics_fields",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= approved_on", name="ck_ethics_dates"
        ),
        sa.ForeignKeyConstraint(["scholar_id"], ["core.scholars.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_ethics_clearances_scholar_id"),
        "ethics_clearances",
        ["scholar_id"],
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column("require_ethics", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="core",
    )
    _file_owners(OWNERS + ", 'ethics_clearances'")


def downgrade() -> None:
    # Fails loudly while a certificate is attached to a clearance: files are never deleted here.
    _file_owners(OWNERS)
    op.drop_column("settings", "require_ethics", schema="core")
    op.drop_table("ethics_clearances", schema="core")
