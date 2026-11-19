"""the papers of an entry of the PhD file: a signed copy per kind (PRD F17b)

Revision ID: 0046
Revises: 0045
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "'signed_copy', 'notice', 'report', 'attendance', 'drc_minutes', 'drc_notice', 'fee_due', "
    "'corrections', 'examiner_panel', 'invite_national', 'accept_national', "
    "'invite_international', 'accept_international', 'viva_approval', 'viva_board', "
    "'viva_notice', 'viva_examiner_email', 'viva_report'"
)


def upgrade() -> None:
    op.add_column(
        "signed_copies",
        sa.Column("kind", sa.Text(), server_default=sa.text("'signed_copy'"), nullable=False),
        schema="core",
    )
    op.create_check_constraint(
        "ck_signed_copies_kind", "signed_copies", f"kind IN ({KINDS})", schema="core"
    )
    # Copies made before kinds: each was the entry's main paper.
    for kind, where in (
        ("report", "record_id IN (SELECT id FROM core.seminar_scholars)"),
        ("drc_minutes", "annexure = 'decisions'"),
        ("viva_approval", "record_id IN (SELECT id FROM core.viva_arrangements)"),
        ("viva_report", "record_id IN (SELECT id FROM core.vivas)"),
    ):
        op.execute(f"UPDATE core.signed_copies SET kind = '{kind}' WHERE {where}")


def downgrade() -> None:
    op.drop_constraint("ck_signed_copies_kind", "signed_copies", schema="core", type_="check")
    op.drop_column("signed_copies", "kind", schema="core")
