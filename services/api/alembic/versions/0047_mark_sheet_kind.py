"""the coursework mark sheet as a paper of the PhD file (PRD F17b)

Revision ID: 0047
Revises: 0046
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "'signed_copy', 'notice', 'report', 'attendance', 'drc_minutes', 'drc_notice', 'fee_due', "
    "'corrections', 'examiner_panel', 'invite_national', 'accept_national', "
    "'invite_international', 'accept_international', 'viva_approval', 'viva_board', "
    "'viva_notice', 'viva_examiner_email', 'viva_report'"
)


def _kinds(kinds: str) -> None:
    op.drop_constraint("ck_signed_copies_kind", "signed_copies", schema="core", type_="check")
    op.create_check_constraint(
        "ck_signed_copies_kind", "signed_copies", f"kind IN ({kinds})", schema="core"
    )


def upgrade() -> None:
    _kinds(KINDS + ", 'mark_sheet'")


def downgrade() -> None:
    op.execute(
        "DELETE FROM core.files WHERE table_name = 'signed_copies' AND record_id IN"
        " (SELECT id FROM core.signed_copies WHERE kind = 'mark_sheet')"
    )
    op.execute("DELETE FROM core.signed_copies WHERE kind = 'mark_sheet'")
    _kinds(KINDS)
