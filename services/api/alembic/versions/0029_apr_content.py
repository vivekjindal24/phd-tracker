"""progress report sections, files, template setting and approver ratings

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNERS = (
    "'scholars', 'publications', 'conferences', 'documents', 'thesis_submissions', "
    "'examiner_reports', 'vivas', 'shodhganga_deposits', 'utilisation_certificates', "
    "'thesis_reviews', 'ethics_clearances'"
)
STANDARD = (
    '[{"name": "Work done this period", "hint": "Experiments, fieldwork, reading and writing."}, '
    '{"name": "Progress against objectives", '
    '"hint": "Each objective of the proposal: where it stands."}, '
    '{"name": "Difficulties faced", "hint": "Anything that slowed the work, and what would help."}, '
    '{"name": "Plan for the next six months", "hint": "What will be done, and by when."}]'
)


def _file_owners(owners: str) -> None:
    op.drop_constraint("ck_files_owner", "files", schema="core", type_="check")
    op.create_check_constraint(
        "ck_files_owner", "files", f"table_name IN ({owners})", schema="core"
    )


def upgrade() -> None:
    op.add_column(
        "progress_reports",
        sa.Column(
            "sections", postgresql.JSONB(), server_default=sa.text("'[]'"), nullable=False
        ),
        schema="core",
    )
    op.add_column("approval_actions", sa.Column("rating", sa.Text()), schema="core")
    op.create_check_constraint(
        "ck_actions_rating",
        "approval_actions",
        "rating IS NULL OR (action = 'approve' AND rating IN "
        "('satisfactory', 'needs_improvement', 'unsatisfactory'))",
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column(
            "apr_custom_template", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column(
            "apr_sections",
            postgresql.JSONB(),
            server_default=sa.text(f"'{STANDARD}'::jsonb"),
            nullable=False,
        ),
        schema="core",
    )
    op.create_check_constraint(
        "ck_settings_apr_sections",
        "settings",
        "jsonb_typeof(apr_sections) = 'array' AND jsonb_array_length(apr_sections) > 0",
        schema="core",
    )
    _file_owners(OWNERS + ", 'progress_reports'")


def downgrade() -> None:
    # Fails loudly while a file hangs off a progress report: files are never deleted here.
    _file_owners(OWNERS)
    op.drop_column("settings", "apr_sections", schema="core")
    op.drop_column("settings", "apr_custom_template", schema="core")
    op.drop_column("approval_actions", "rating", schema="core")
    op.drop_column("progress_reports", "sections", schema="core")
