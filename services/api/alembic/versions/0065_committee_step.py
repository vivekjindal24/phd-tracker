"""advisory committee approval step (PRD F9b): a step kind a university may add to the progress
report chain

Revision ID: 0065
Revises: 0064
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS_OLD = (
    "'supervisor', 'department', 'research_office', 'exam_office', 'library', 'vice_chancellor'"
)
KINDS_NEW = KINDS_OLD + ", 'committee'"


def _check(kinds: str) -> None:
    op.drop_constraint("ck_actions_step_kind", "approval_actions", schema="core", type_="check")
    op.create_check_constraint(
        "ck_actions_step_kind",
        "approval_actions",
        f"step_kind IS NULL OR step_kind IN ({kinds})",
        schema="core",
    )


def upgrade() -> None:
    _check(KINDS_NEW)


def downgrade() -> None:
    # Fails loudly once a committee has acted (approval history is never deleted by a migration).
    _check(KINDS_OLD)
