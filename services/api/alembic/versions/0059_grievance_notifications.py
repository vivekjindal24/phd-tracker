"""a notification category of its own for grievances, which nobody can mute

Revision ID: 0059
Revises: 0058
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = (
    "'approval_waiting', 'sent_back', 'approved', 'apr_due', 'meeting_tomorrow', "
    "'fellowship_ending', 'grant_alert', 'seminar', 'notice', 'system'"
)


def _categories(values: str) -> None:
    for name, table, expr in (
        ("ck_notifications_category", "notifications", f"category IN ({values})"),
        ("ck_users_email_muted", "users", f"email_muted <@ ARRAY[{values}]::text[]"),
        ("ck_users_whatsapp_muted", "users", f"whatsapp_muted <@ ARRAY[{values}]::text[]"),
    ):
        op.drop_constraint(name, table, schema="core")
        op.create_check_constraint(name, table, expr, schema="core")


def upgrade() -> None:
    _categories(CATEGORIES + ", 'grievance'")
    op.execute(
        "UPDATE core.notifications SET category = 'grievance' "
        "WHERE category = 'system' AND link LIKE '/grievances/%'"
    )


def downgrade() -> None:
    op.execute("UPDATE core.notifications SET category = 'system' WHERE category = 'grievance'")
    _categories(CATEGORIES)
