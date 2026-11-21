"""the notice board: notices for the university or a department, the notice category, and
a notice's file

Revision ID: 0054
Revises: 0053
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = (
    "'approval_waiting', 'sent_back', 'approved', 'apr_due', 'meeting_tomorrow', "
    "'fellowship_ending', 'grant_alert', 'seminar', 'system'"
)
OWNERS = (
    "'scholars', 'progress_reports', 'publications', 'conferences', 'documents', "
    "'thesis_submissions', 'examiner_reports', 'vivas', 'shodhganga_deposits', "
    "'utilisation_certificates', 'thesis_reviews', 'ethics_clearances', 'signed_copies'"
)


def _categories(values: str) -> None:
    for name, table, expr in (
        ("ck_notifications_category", "notifications", f"category IN ({values})"),
        ("ck_users_email_muted", "users", f"email_muted <@ ARRAY[{values}]::text[]"),
        ("ck_users_whatsapp_muted", "users", f"whatsapp_muted <@ ARRAY[{values}]::text[]"),
    ):
        op.drop_constraint(name, table, schema="core")
        op.create_check_constraint(name, table, expr, schema="core")


def _owners(values: str) -> None:
    op.drop_constraint("ck_files_owner", "files", schema="core", type_="check")
    op.create_check_constraint("ck_files_owner", "files", f"table_name IN ({values})", schema="core")


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("unit_id", UUID(as_uuid=True), sa.ForeignKey("core.org_units.id")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ends_on", sa.Date()),
        sa.Column("posted_by", UUID(as_uuid=True), sa.ForeignKey("core.users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="ck_announcements_title"),
        sa.CheckConstraint("char_length(body) <= 5000", name="ck_announcements_body"),
        schema="core",
    )
    op.create_index("ix_announcements_unit_id", "announcements", ["unit_id"], schema="core")
    _categories(CATEGORIES + ", 'notice'")
    _owners(OWNERS + ", 'announcements'")


def downgrade() -> None:
    op.execute("UPDATE core.notifications SET category = 'system' WHERE category = 'notice'")
    op.execute(
        "UPDATE core.users SET email_muted = array_remove(email_muted, 'notice'), "
        "whatsapp_muted = array_remove(whatsapp_muted, 'notice')"
    )
    _categories(CATEGORIES)
    op.execute(
        "DELETE FROM core.files WHERE table_name = 'announcements'"
    )
    _owners(OWNERS)
    op.drop_table("announcements", schema="core")
