"""grant alerts: the grant_alert notification category

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0017'
down_revision: str | None = '0016'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "'approval_waiting', 'sent_back', 'approved', 'apr_due', 'meeting_tomorrow', 'fellowship_ending', 'seminar', 'system'"
NEW = "'approval_waiting', 'sent_back', 'approved', 'apr_due', 'meeting_tomorrow', 'fellowship_ending', 'grant_alert', 'seminar', 'system'"


def _categories(values: str) -> None:
    for name, table, expr in (
        ('ck_notifications_category', 'notifications', f"category IN ({values})"),
        ('ck_users_email_muted', 'users', f"email_muted <@ ARRAY[{values}]::text[]"),
        ('ck_users_whatsapp_muted', 'users', f"whatsapp_muted <@ ARRAY[{values}]::text[]"),
    ):
        op.drop_constraint(name, table, schema='core')
        op.create_check_constraint(name, table, expr, schema='core')


def upgrade() -> None:
    _categories(NEW)


def downgrade() -> None:
    op.execute("UPDATE core.notifications SET category = 'system' WHERE category = 'grant_alert'")
    op.execute("UPDATE core.users SET email_muted = array_remove(email_muted, 'grant_alert'), whatsapp_muted = array_remove(whatsapp_muted, 'grant_alert')")
    _categories(OLD)
