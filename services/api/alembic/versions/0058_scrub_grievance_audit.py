"""scrub grievance words out of audit rows written before they were redacted (crud.py)

Revision ID: 0058
Revises: 0057
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORDS = ("subject", "description", "decision", "appeal_reason", "appeal_decision")
FILE_NAMES = ("file_name", "storage_key")


def _scrub(keys: tuple[str, ...], where: str) -> None:
    """Each key present in a snapshot becomes "[redacted]"; absent or null keys stay as they are."""
    for column in ("data", "prev"):
        for key in keys:
            op.execute(
                f"UPDATE core.audit_log SET {column} = jsonb_set({column}, '{{{key}}}', "
                f"'\"[redacted]\"') WHERE {where} AND {column} ? '{key}' "
                f"AND {column}->>'{key}' IS NOT NULL"
            )


def upgrade() -> None:
    _scrub(WORDS, "table_name = 'grievances'")
    _scrub(FILE_NAMES, "table_name = 'files' AND data->>'table_name' = 'grievances'")


def downgrade() -> None:
    """Nothing to restore: the words were never meant to be there."""
