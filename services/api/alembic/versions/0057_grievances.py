"""grievances: the grievance cell and Ombudsperson roles, the grievances table, their files and
who decides appeals

Revision ID: 0057
Revises: 0056
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OFFICES = "'research_office', 'exam_office', 'library', 'vice_chancellor'"
GRIEVANCE_ROLES = "'grievance_cell', 'ombudsperson'"
OWNERS = (
    "'scholars', 'progress_reports', 'publications', 'conferences', 'documents', "
    "'thesis_submissions', 'examiner_reports', 'vivas', 'shodhganga_deposits', "
    "'utilisation_certificates', 'thesis_reviews', 'ethics_clearances', 'signed_copies', "
    "'announcements'"
)
CATEGORIES = "'supervision', 'evaluation', 'coursework', 'fellowship', 'administration', 'other'"
STATUSES = "'open', 'decided', 'closed', 'appealed', 'appeal_decided', 'withdrawn'"


def _roles(offices: str) -> None:
    for name in ("ck_role_assignments_role", "ck_role_scope"):
        op.drop_constraint(name, "role_assignments", schema="core", type_="check")
    op.create_check_constraint(
        "ck_role_assignments_role",
        "role_assignments",
        f"role IN ('unit_head', 'admin', {offices})",
        schema="core",
    )
    op.create_check_constraint(
        "ck_role_scope",
        "role_assignments",
        "(role IN ('unit_head', 'admin') AND unit_id IS NOT NULL)"
        f" OR (role IN ({offices}) AND unit_id IS NULL)",
        schema="core",
    )


def _owners(values: str) -> None:
    op.drop_constraint("ck_files_owner", "files", schema="core", type_="check")
    op.create_check_constraint(
        "ck_files_owner", "files", f"table_name IN ({values})", schema="core"
    )


def upgrade() -> None:
    _roles(f"{OFFICES}, {GRIEVANCE_ROLES}")
    op.create_table(
        "grievances",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("scholar_id", UUID(as_uuid=True), sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("decision", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by", UUID(as_uuid=True), sa.ForeignKey("core.users.id")),
        sa.Column("appeal_reason", sa.Text()),
        sa.Column("appealed_at", sa.DateTime(timezone=True)),
        sa.Column("appeal_decision", sa.Text()),
        sa.Column("appeal_decided_at", sa.DateTime(timezone=True)),
        sa.Column("appeal_decided_by", UUID(as_uuid=True), sa.ForeignKey("core.users.id")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"category IN ({CATEGORIES})", name="ck_grievances_category"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_grievances_status"),
        sa.CheckConstraint("char_length(subject) BETWEEN 1 AND 200", name="ck_grievances_subject"),
        sa.CheckConstraint(
            "char_length(description) BETWEEN 1 AND 5000", name="ck_grievances_description"
        ),
        schema="core",
    )
    op.create_index("ix_grievances_scholar_id", "grievances", ["scholar_id"], schema="core")
    _owners(OWNERS + ", 'grievances'")
    op.add_column(
        "settings",
        sa.Column("grievance_appeals_to", sa.Text(), nullable=False, server_default="ombudsperson"),
        schema="core",
    )
    op.create_check_constraint(
        "ck_settings_appeals_to",
        "settings",
        "grievance_appeals_to IN ('ombudsperson', 'vice_chancellor')",
        schema="core",
    )


def downgrade() -> None:
    op.drop_constraint("ck_settings_appeals_to", "settings", schema="core", type_="check")
    op.drop_column("settings", "grievance_appeals_to", schema="core")
    op.execute("DELETE FROM core.files WHERE table_name = 'grievances'")
    _owners(OWNERS)
    op.drop_table("grievances", schema="core")
    op.execute(
        "DELETE FROM core.role_assignments WHERE role IN ('grievance_cell', 'ombudsperson')"
    )
    _roles(OFFICES)
