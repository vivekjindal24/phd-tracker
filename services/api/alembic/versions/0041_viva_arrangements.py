"""viva arrangements: approval to hold the viva (Form X) and its board (Form XI), PRD M3

Revision ID: 0041
Revises: 0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")
LIVE = sa.text("deleted_at IS NULL")

ITEMS_OLD = (
    "'progress_report', 'publication', 'coursework_clearance', 'thesis_submission', "
    "'no_dues_clearance', 'fellowship_claim'"
)
ITEMS_NEW = ITEMS_OLD + ", 'viva_arrangement'"
TARGETS_OLD = (
    "'scholars', 'meetings', 'progress_reports', 'milestones', 'publications', 'conferences', "
    "'documents', 'thesis_submissions', 'coursework_clearances', 'no_dues_clearances', "
    "'fellowship_claims'"
)
TARGETS_NEW = TARGETS_OLD + ", 'viva_arrangements'"
VIVA_CHAIN = '[{"kind": "vice_chancellor"}]'


def _checks(items: str, targets: str) -> None:
    for name, table, expr in (
        ("ck_chains_item_type", "approval_chains", f"item_type IN ({items})"),
        ("ck_actions_item_type", "approval_actions", f"item_type IN ({items})"),
        ("ck_signing_codes_item", "signing_codes", f"item_type IN ({items})"),
        ("ck_comments_target", "comments", f"table_name IN ({targets})"),
    ):
        op.drop_constraint(name, table, schema="core", type_="check")
        op.create_check_constraint(name, table, expr, schema="core")


def _row_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def upgrade() -> None:
    op.create_table(
        "viva_arrangements",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("thesis_id", UUID, sa.ForeignKey("core.thesis_submissions.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("venue", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("online_link", sa.Text()),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True)),
        sa.Column("state", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("current_step", sa.Integer()),
        sa.Column("chain_snapshot", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        *_row_columns(),
        sa.CheckConstraint(
            "state IN ('draft', 'in_review', 'sent_back', 'approved')",
            name="ck_viva_arrangements_state",
        ),
        sa.CheckConstraint(
            "(current_step IS NOT NULL) = (state = 'in_review')",
            name="ck_viva_arrangements_step",
        ),
        schema="core",
    )
    for column in ("scholar_id", "thesis_id"):
        op.create_index(
            op.f(f"ix_core_viva_arrangements_{column}"),
            "viva_arrangements",
            [column],
            schema="core",
        )
    op.create_table(
        "viva_board_members",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "arrangement_id", UUID, sa.ForeignKey("core.viva_arrangements.id"), nullable=False
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("faculty_id", UUID, sa.ForeignKey("core.faculty.id")),
        sa.Column("name", sa.Text()),
        sa.Column("institution", sa.Text()),
        sa.Column("email", postgresql.CITEXT()),
        *_row_columns(),
        sa.CheckConstraint(
            "role IN ('chairperson', 'external_examiner', 'member')", name="ck_viva_board_role"
        ),
        sa.CheckConstraint(
            "(faculty_id IS NOT NULL AND name IS NULL AND institution IS NULL AND email IS NULL)"
            " OR (faculty_id IS NULL AND name IS NOT NULL AND institution IS NOT NULL"
            " AND email IS NOT NULL)",
            name="ck_viva_board_kind",
        ),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_viva_board_members_arrangement_id"),
        "viva_board_members",
        ["arrangement_id"],
        schema="core",
    )
    op.create_index(
        "uq_viva_board_faculty",
        "viva_board_members",
        ["arrangement_id", "faculty_id"],
        unique=True,
        postgresql_where=LIVE,
        schema="core",
    )
    op.create_index(
        "uq_viva_board_chair",
        "viva_board_members",
        ["arrangement_id"],
        unique=True,
        postgresql_where=sa.text("role = 'chairperson' AND deleted_at IS NULL"),
        schema="core",
    )
    op.add_column(
        "vivas",
        sa.Column("arrangement_id", UUID, sa.ForeignKey("core.viva_arrangements.id")),
        schema="core",
    )
    _checks(ITEMS_NEW, TARGETS_NEW)
    op.execute(
        "INSERT INTO core.approval_chains (item_type, steps) "
        f"VALUES ('viva_arrangement', '{VIVA_CHAIN}'::jsonb)"
    )


def downgrade() -> None:
    # The tables go, so their chain, actions, codes and comments go with them (a rollback).
    for table, column in (
        ("approval_chains", "item_type"),
        ("approval_actions", "item_type"),
        ("signing_codes", "item_type"),
    ):
        op.execute(f"DELETE FROM core.{table} WHERE {column} = 'viva_arrangement'")
    op.execute("DELETE FROM core.comments WHERE table_name = 'viva_arrangements'")
    _checks(ITEMS_OLD, TARGETS_OLD)
    op.drop_column("vivas", "arrangement_id", schema="core")
    op.drop_table("viva_board_members", schema="core")
    op.drop_table("viva_arrangements", schema="core")
