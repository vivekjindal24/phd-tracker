"""patents: a module of its own, the patents table and its files, and who verifies them; the
faculty papers' library_note becomes return_note (verification.py serves both)

Revision ID: 0062
Revises: 0061
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODULES = (
    "'publications', 'conferences', 'documents', 'coursework', 'admissions', 'fellowships', "
    "'projects', 'ledger'"
)
OWNERS = (
    "'scholars', 'progress_reports', 'publications', 'conferences', 'documents', "
    "'thesis_submissions', 'examiner_reports', 'vivas', 'shodhganga_deposits', "
    "'utilisation_certificates', 'thesis_reviews', 'ethics_clearances', 'signed_copies', "
    "'announcements', 'grievances', 'faculty_publications'"
)


def _check(name: str, table: str, expr: str) -> None:
    op.drop_constraint(name, table, schema="core", type_="check")
    op.create_check_constraint(name, table, expr, schema="core")


def upgrade() -> None:
    op.alter_column(
        "faculty_publications", "library_note", new_column_name="return_note", schema="core"
    )
    _check("ck_modules_key", "modules", f"key IN ({MODULES}, 'patents')")
    op.execute("INSERT INTO core.modules (key) VALUES ('patents')")
    op.create_table(
        "patents",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("faculty_id", UUID(as_uuid=True), sa.ForeignKey("core.faculty.id")),
        sa.Column("scholar_id", UUID(as_uuid=True), sa.ForeignKey("core.scholars.id")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("inventors", sa.Text(), nullable=False),
        sa.Column("application_number", sa.Text(), nullable=False),
        sa.Column("filed_on", sa.Date(), nullable=False),
        sa.Column("office", sa.Text(), nullable=False),
        sa.Column("patent_status", sa.Text(), nullable=False),
        sa.Column("published_on", sa.Date()),
        sa.Column("granted_on", sa.Date()),
        sa.Column("patent_number", sa.Text()),
        sa.Column("verification", sa.Text(), nullable=False, server_default="waiting"),
        sa.Column("return_note", sa.Text()),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("checked_by", UUID(as_uuid=True), sa.ForeignKey("core.users.id")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "verification IN ('waiting', 'returned', 'verified')", name="ck_patents_verification"
        ),
        sa.CheckConstraint(
            "(verification = 'waiting' AND checked_at IS NULL)"
            " OR (verification = 'verified' AND checked_at IS NOT NULL)"
            " OR (verification = 'returned' AND checked_at IS NOT NULL AND return_note <> '')",
            name="ck_patents_check",
        ),
        sa.CheckConstraint("(faculty_id IS NULL) <> (scholar_id IS NULL)", name="ck_patents_owner"),
        sa.CheckConstraint(
            "patent_status IN ('filed', 'published', 'granted')", name="ck_patents_status"
        ),
        sa.CheckConstraint(
            "(patent_status <> 'published' OR published_on IS NOT NULL)"
            " AND (patent_status <> 'granted' OR (granted_on IS NOT NULL"
            " AND patent_number IS NOT NULL))"
            " AND (published_on IS NULL OR published_on >= filed_on)"
            " AND (granted_on IS NULL OR granted_on >= filed_on)",
            name="ck_patents_dates",
        ),
        schema="core",
    )
    op.create_index("ix_core_patents_faculty_id", "patents", ["faculty_id"], schema="core")
    op.create_index("ix_core_patents_scholar_id", "patents", ["scholar_id"], schema="core")
    op.create_index(
        "ix_patents_title_trgm",
        "patents",
        ["title"],
        schema="core",
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    _check("ck_files_owner", "files", f"table_name IN ({OWNERS}, 'patents')")
    op.add_column(
        "settings",
        sa.Column("patent_verifier", sa.Text(), nullable=False, server_default="research_office"),
        schema="core",
    )
    op.create_check_constraint(
        "ck_settings_patent_verifier",
        "settings",
        "patent_verifier IN ('research_office', 'library')",
        schema="core",
    )


def downgrade() -> None:
    op.drop_constraint("ck_settings_patent_verifier", "settings", schema="core", type_="check")
    op.drop_column("settings", "patent_verifier", schema="core")
    op.execute("DELETE FROM core.files WHERE table_name = 'patents'")
    _check("ck_files_owner", "files", f"table_name IN ({OWNERS})")
    op.drop_table("patents", schema="core")
    op.execute("DELETE FROM core.modules WHERE key = 'patents'")
    _check("ck_modules_key", "modules", f"key IN ({MODULES})")
    op.alter_column(
        "faculty_publications", "return_note", new_column_name="library_note", schema="core"
    )
