"""a file refused by the virus scanner is kept as a soft-deleted row marked infected, its
object removed from storage (scanner.py)

Revision ID: 0067
Revises: 0066
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _check(values: str) -> None:
    op.drop_constraint("ck_files_status", "files", schema="core", type_="check")
    op.create_check_constraint("ck_files_status", "files", f"status IN ({values})", schema="core")


def upgrade() -> None:
    _check("'pending', 'ready', 'infected'")


def downgrade() -> None:
    # Fails loudly once a file has been refused (records are never deleted by a migration).
    _check("'pending', 'ready'")
