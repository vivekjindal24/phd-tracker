"""switch two-factor login off (owner request: the demo install has only dummy logins)

A data change, not DDL. It runs once per install; a fresh install already starts with the
setting off. Turn it back on in Settings before a real university goes live.

Revision ID: 0034
Revises: 0033
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO core.audit_log (table_name, record_id, action, prev, data)
        SELECT 'settings', '1', 'update',
               '{"require_two_factor": true}'::jsonb, '{"require_two_factor": false}'::jsonb
        FROM core.settings WHERE id = 1 AND require_two_factor
        """
    )
    op.execute("UPDATE core.settings SET require_two_factor = false WHERE id = 1")


def downgrade() -> None:
    """Nothing to undo: whether two-factor is on is the admin's choice in Settings."""
