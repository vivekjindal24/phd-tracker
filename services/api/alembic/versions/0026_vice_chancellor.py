"""vice chancellor role and chain step

Revision ID: 0026
Revises: 0025
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OFFICES_OLD = "'research_office', 'exam_office', 'library'"
OFFICES_NEW = OFFICES_OLD + ", 'vice_chancellor'"


def _checks(offices: str) -> None:
    for name, table, expr in (
        (
            "ck_role_assignments_role",
            "role_assignments",
            f"role IN ('unit_head', 'admin', {offices})",
        ),
        (
            "ck_role_scope",
            "role_assignments",
            "(role IN ('unit_head', 'admin') AND unit_id IS NOT NULL)"
            f" OR (role IN ({offices}) AND unit_id IS NULL)",
        ),
        (
            "ck_actions_step_kind",
            "approval_actions",
            f"step_kind IS NULL OR step_kind IN ('supervisor', 'department', {offices})",
        ),
    ):
        op.drop_constraint(name, table, schema="core", type_="check")
        op.create_check_constraint(name, table, expr, schema="core")


def upgrade() -> None:
    _checks(OFFICES_NEW)


def downgrade() -> None:
    # Fails loudly while a Vice Chancellor is assigned, acted, or sits in a chain: remove those
    # first (role assignments and approval history are never deleted by a migration).
    _checks(OFFICES_OLD)
