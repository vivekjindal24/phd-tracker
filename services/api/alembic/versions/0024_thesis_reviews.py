"""thesis reviews

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNERS = (
    "'scholars', 'publications', 'conferences', 'documents', 'thesis_submissions', "
    "'examiner_reports', 'vivas', 'shodhganga_deposits', 'utilisation_certificates'"
)
ACTIONS = "'insert', 'update', 'soft_delete', 'restore', 'transition'"


def _file_owners(owners: str) -> None:
    op.drop_constraint("ck_files_owner", "files", schema="core", type_="check")
    op.create_check_constraint(
        "ck_files_owner", "files", f"table_name IN ({owners})", schema="core"
    )


def _row() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _audit_actions(actions: str) -> None:
    op.drop_constraint("ck_audit_action", "audit_log", schema="core", type_="check")
    op.create_check_constraint(
        "ck_audit_action", "audit_log", f"action IN ({actions})", schema="core"
    )


def upgrade() -> None:
    _audit_actions(ACTIONS + ", 'lookup'")
    op.add_column(
        "users",
        sa.Column("is_reviewer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="core",
    )
    op.create_table(
        "thesis_reviews",
        sa.Column("thesis_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_user_id", sa.UUID(), nullable=True),
        sa.Column("report_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("institution", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("allow_download", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'invited'"), nullable=False),
        sa.Column("invite_token_hash", sa.Text(), nullable=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *_row(),
        sa.CheckConstraint(
            "status IN ('invited', 'accepted', 'declined', 'expired', 'submitted')",
            name="ck_thesis_reviews_status",
        ),
        sa.CheckConstraint(
            "recommendation IS NULL OR recommendation IN "
            "('accept', 'minor_revision', 'major_revision', 'reject')",
            name="ck_thesis_reviews_rec",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["core.examiner_reports.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["core.users.id"]),
        sa.ForeignKeyConstraint(["thesis_id"], ["core.thesis_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_thesis_reviews_thesis_id"), "thesis_reviews", ["thesis_id"], schema="core"
    )
    op.create_index(
        op.f("ix_core_thesis_reviews_reviewer_user_id"),
        "thesis_reviews",
        ["reviewer_user_id"],
        schema="core",
    )
    op.create_index(
        "uq_thesis_review_active",
        "thesis_reviews",
        ["thesis_id", "email"],
        unique=True,
        schema="core",
        postgresql_where=sa.text(
            "deleted_at IS NULL AND status IN ('invited', 'accepted', 'submitted')"
        ),
    )
    op.create_index(
        "uq_thesis_review_token",
        "thesis_reviews",
        ["invite_token_hash"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("invite_token_hash IS NOT NULL"),
    )
    op.create_table(
        "thesis_review_comments",
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        *_row(),
        sa.CheckConstraint("page >= 1", name="ck_review_comments_page"),
        sa.ForeignKeyConstraint(["review_id"], ["core.thesis_reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_thesis_review_comments_review_id"),
        "thesis_review_comments",
        ["review_id"],
        schema="core",
    )
    op.create_table(
        "thesis_review_copies",
        sa.Column("review_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        *_row(),
        sa.CheckConstraint("kind IN ('view', 'download')", name="ck_review_copies_kind"),
        sa.ForeignKeyConstraint(["review_id"], ["core.thesis_reviews.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_review_copy_code"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_thesis_review_copies_review_id"),
        "thesis_review_copies",
        ["review_id"],
        schema="core",
    )
    _file_owners(OWNERS + ", 'thesis_reviews'")


def downgrade() -> None:
    # ck_audit_action stays wide: audit rows are never deleted, so 'lookup' rows must stay valid.
    _file_owners(OWNERS)
    op.drop_table("thesis_review_copies", schema="core")
    op.drop_table("thesis_review_comments", schema="core")
    op.drop_table("thesis_reviews", schema="core")
    op.drop_column("users", "is_reviewer", schema="core")
