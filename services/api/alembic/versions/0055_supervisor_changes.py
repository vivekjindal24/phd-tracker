"""change of supervisor through an approval chain

Revision ID: 0055
Revises: 0054
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")
ITEMS_OLD = (
    "'progress_report', 'publication', 'coursework_clearance', 'thesis_submission', "
    "'no_dues_clearance', 'fellowship_claim', 'viva_arrangement'"
)
ITEMS_NEW = ITEMS_OLD + ", 'supervisor_change'"
TARGETS_OLD = (
    "'scholars', 'meetings', 'progress_reports', 'milestones', 'publications', 'conferences', "
    "'documents', 'thesis_submissions', 'coursework_clearances', 'no_dues_clearances', "
    "'fellowship_claims', 'viva_arrangements'"
)
TARGETS_NEW = TARGETS_OLD + ", 'supervisor_changes'"
CHAIN = '[{"kind": "department"}, {"kind": "research_office"}]'


def _checks(items: str, targets: str) -> None:
    for name, table, expr in (
        ("ck_chains_item_type", "approval_chains", f"item_type IN ({items})"),
        ("ck_actions_item_type", "approval_actions", f"item_type IN ({items})"),
        ("ck_signing_codes_item", "signing_codes", f"item_type IN ({items})"),
        ("ck_comments_target", "comments", f"table_name IN ({targets})"),
    ):
        op.drop_constraint(name, table, schema="core", type_="check")
        op.create_check_constraint(name, table, expr, schema="core")


def upgrade() -> None:
    op.create_table(
        "supervisor_changes",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("from_faculty_id", UUID, sa.ForeignKey("core.faculty.id")),
        sa.Column("to_faculty_id", UUID, sa.ForeignKey("core.faculty.id"), nullable=False),
        sa.Column("from_name", sa.Text()),
        sa.Column("to_name", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("scholar_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("order_ref", sa.Text()),
        sa.Column("effective_on", sa.Date()),
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
            name="ck_supervisor_changes_state",
        ),
        sa.CheckConstraint(
            "(current_step IS NOT NULL) = (state = 'in_review')", name="ck_supervisor_changes_step"
        ),
        sa.CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 2000", name="ck_supervisor_changes_reason"
        ),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_supervisor_changes_scholar_id"),
        "supervisor_changes",
        ["scholar_id"],
        schema="core",
    )
    op.create_index(
        "uq_supervisor_change_open",
        "supervisor_changes",
        ["scholar_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("state <> 'approved' AND deleted_at IS NULL"),
    )
    _checks(ITEMS_NEW, TARGETS_NEW)
    op.execute(
        "INSERT INTO core.approval_chains (item_type, steps) "
        f"VALUES ('supervisor_change', '{CHAIN}'::jsonb)"
    )


def downgrade() -> None:
    for table, column in (
        ("approval_chains", "item_type"),
        ("approval_actions", "item_type"),
        ("signing_codes", "item_type"),
    ):
        op.execute(f"DELETE FROM core.{table} WHERE {column} = 'supervisor_change'")
    op.execute("DELETE FROM core.comments WHERE table_name = 'supervisor_changes'")
    _checks(ITEMS_OLD, TARGETS_OLD)
    op.drop_table("supervisor_changes", schema="core")
