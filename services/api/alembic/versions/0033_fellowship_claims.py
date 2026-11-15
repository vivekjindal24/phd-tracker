"""fellowship monthly claims

Revision ID: 0033
Revises: 0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")

ITEMS_OLD = (
    "'progress_report', 'publication', 'coursework_clearance', 'thesis_submission', "
    "'no_dues_clearance'"
)
ITEMS_NEW = ITEMS_OLD + ", 'fellowship_claim'"
TARGETS_OLD = (
    "'scholars', 'meetings', 'progress_reports', 'milestones', 'publications', 'conferences', "
    "'documents', 'thesis_submissions', 'coursework_clearances', 'no_dues_clearances'"
)
TARGETS_NEW = TARGETS_OLD + ", 'fellowship_claims'"
CLAIM_CHAIN = '[{"kind": "supervisor"}, {"kind": "department"}, {"kind": "research_office"}]'


def _checks(items: str, targets: str) -> None:
    for name, table, expr in (
        ("ck_chains_item_type", "approval_chains", f"item_type IN ({items})"),
        ("ck_actions_item_type", "approval_actions", f"item_type IN ({items})"),
        ("ck_comments_target", "comments", f"table_name IN ({targets})"),
    ):
        op.drop_constraint(name, table, schema="core", type_="check")
        op.create_check_constraint(name, table, expr, schema="core")


def upgrade() -> None:
    op.create_table(
        "fellowship_claims",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("fellowship_id", UUID, sa.ForeignKey("core.fellowships.id"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("leave_days", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("state", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("current_step", sa.Integer()),
        sa.Column("chain_snapshot", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "state IN ('draft', 'in_review', 'sent_back', 'approved')",
            name="ck_fellowship_claims_state",
        ),
        sa.CheckConstraint(
            "(current_step IS NOT NULL) = (state = 'in_review')", name="ck_fellowship_claims_step"
        ),
        sa.CheckConstraint("extract(day FROM month) = 1", name="ck_fellowship_claims_month"),
        sa.CheckConstraint("leave_days BETWEEN 0 AND 31", name="ck_fellowship_claims_leave"),
        sa.CheckConstraint("amount >= 0", name="ck_fellowship_claims_amount"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_fellowship_claims_scholar_id"),
        "fellowship_claims",
        ["scholar_id"],
        schema="core",
    )
    op.create_index(
        "uq_fellowship_claim_month",
        "fellowship_claims",
        ["fellowship_id", "month"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    _checks(ITEMS_NEW, TARGETS_NEW)
    op.execute(
        "INSERT INTO core.approval_chains (item_type, steps) "
        f"VALUES ('fellowship_claim', '{CLAIM_CHAIN}'::jsonb)"
    )


def downgrade() -> None:
    # The table goes, so its chain, actions and comments go with it (a schema rollback).
    op.execute("DELETE FROM core.approval_chains WHERE item_type = 'fellowship_claim'")
    op.execute("DELETE FROM core.approval_actions WHERE item_type = 'fellowship_claim'")
    op.execute("DELETE FROM core.comments WHERE table_name = 'fellowship_claims'")
    _checks(ITEMS_OLD, TARGETS_OLD)
    op.drop_table("fellowship_claims", schema="core")
