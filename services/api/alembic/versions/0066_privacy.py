"""privacy (DPDP Act 2023): the university's privacy notice and who answers data requests,
when each person last read the notice, data requests, and their unmutable notification category

Revision ID: 0066
Revises: 0065
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")
CATEGORIES = (
    "'approval_waiting', 'sent_back', 'approved', 'apr_due', 'meeting_tomorrow', "
    "'fellowship_ending', 'grant_alert', 'seminar', 'notice', 'system', 'grievance'"
)


def _categories(values: str) -> None:
    op.drop_constraint("ck_notifications_category", "notifications", schema="core")
    op.create_check_constraint(
        "ck_notifications_category", "notifications", f"category IN ({values})", schema="core"
    )


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("privacy_notice", sa.Text(), server_default="", nullable=False),
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column("privacy_notice_changed_at", sa.DateTime(timezone=True)),
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column("privacy_officer_id", UUID, sa.ForeignKey("core.users.id")),
        schema="core",
    )
    op.add_column(
        "users", sa.Column("privacy_notice_seen_at", sa.DateTime(timezone=True)), schema="core"
    )
    op.create_table(
        "data_requests",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID, sa.ForeignKey("core.users.id"), nullable=False, index=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text()),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("answered_by", UUID, sa.ForeignKey("core.users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "kind IN ('correction', 'erasure', 'other')", name="ck_data_requests_kind"
        ),
        sa.CheckConstraint("status IN ('open', 'answered')", name="ck_data_requests_status"),
        sa.CheckConstraint(
            "char_length(details) BETWEEN 1 AND 3000", name="ck_data_requests_details"
        ),
        sa.CheckConstraint(
            "(status = 'open' AND reply IS NULL AND answered_at IS NULL AND answered_by IS NULL)"
            " OR (status = 'answered' AND char_length(reply) BETWEEN 1 AND 3000"
            " AND answered_at IS NOT NULL AND answered_by IS NOT NULL)",
            name="ck_data_requests_answer",
        ),
        schema="core",
    )
    _categories(CATEGORIES + ", 'data_request'")


def downgrade() -> None:
    op.execute("UPDATE core.notifications SET category = 'system' WHERE category = 'data_request'")
    _categories(CATEGORIES)
    op.drop_table("data_requests", schema="core")
    op.drop_column("users", "privacy_notice_seen_at", schema="core")
    for column in ("privacy_officer_id", "privacy_notice_changed_at", "privacy_notice"):
        op.drop_column("settings", column, schema="core")
