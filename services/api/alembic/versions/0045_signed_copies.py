"""signed copies: the scan of a form signed on paper, per entry of the PhD file (PRD F17b)

Revision ID: 0045
Revises: 0044
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")
OWNERS = (
    "'scholars', 'progress_reports', 'publications', 'conferences', 'documents', "
    "'thesis_submissions', 'examiner_reports', 'vivas', 'shodhganga_deposits', "
    "'utilisation_certificates', 'thesis_reviews', 'ethics_clearances'"
)
ANNEXURES = (
    "'admission', 'employer_noc', 'supervision', 'advisory_committee', 'coursework', "
    "'comprehensive', 'registration_seminar', 'decisions', 'progress', 'publications', "
    "'pre_synopsis_seminar', 'submission', 'examiners', 'viva', 'award', 'copies'"
)


def _file_owners(owners: str) -> None:
    op.drop_constraint("ck_files_owner", "files", schema="core", type_="check")
    op.create_check_constraint(
        "ck_files_owner", "files", f"table_name IN ({owners})", schema="core"
    )


def upgrade() -> None:
    op.create_table(
        "signed_copies",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("annexure", sa.Text(), nullable=False),
        sa.Column("record_id", UUID, nullable=False),
        sa.Column("uploaded_by", UUID, sa.ForeignKey("core.users.id"), nullable=False),
        sa.Column("approved_by", UUID, sa.ForeignKey("core.users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"annexure IN ({ANNEXURES})", name="ck_signed_copies_annexure"),
        sa.CheckConstraint(
            "(approved_by IS NULL) = (approved_at IS NULL)", name="ck_signed_copies_approved"
        ),
        schema="core",
    )
    op.create_index(
        "ix_signed_copies_scholar",
        "signed_copies",
        ["scholar_id"],
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    _file_owners(OWNERS + ", 'signed_copies'")


def downgrade() -> None:
    op.execute("DELETE FROM core.files WHERE table_name = 'signed_copies'")
    _file_owners(OWNERS)
    op.drop_table("signed_copies", schema="core")
