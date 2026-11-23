"""faculty publications: a faculty member's papers, verified by the Library (no chain), and
their files

Revision ID: 0060
Revises: 0059
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNERS = (
    "'scholars', 'progress_reports', 'publications', 'conferences', 'documents', "
    "'thesis_submissions', 'examiner_reports', 'vivas', 'shodhganga_deposits', "
    "'utilisation_certificates', 'thesis_reviews', 'ethics_clearances', 'signed_copies', "
    "'announcements', 'grievances'"
)
T = "faculty_publications"


def _owners(values: str) -> None:
    op.drop_constraint("ck_files_owner", "files", schema="core", type_="check")
    op.create_check_constraint(
        "ck_files_owner", "files", f"table_name IN ({values})", schema="core"
    )


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("faculty_id", UUID(as_uuid=True), sa.ForeignKey("core.faculty.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors", sa.Text(), nullable=False),
        sa.Column("pub_type", sa.Text(), nullable=False),
        sa.Column("venue", sa.Text(), nullable=False),
        sa.Column("issn_isbn", sa.Text()),
        sa.Column(
            "indexing", ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")
        ),
        sa.Column("doi", sa.Text()),
        sa.Column("pub_year", sa.Integer(), nullable=False),
        sa.Column("pub_status", sa.Text(), nullable=False),
        sa.Column("verification", sa.Text(), nullable=False, server_default="waiting"),
        sa.Column("library_note", sa.Text()),
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
            "pub_type IN ('journal', 'conference', 'book_chapter', 'patent')",
            name=f"ck_{T}_type",
        ),
        sa.CheckConstraint(
            "pub_status IN ('submitted', 'accepted', 'published')", name=f"ck_{T}_status"
        ),
        sa.CheckConstraint(
            "indexing <@ ARRAY['scopus', 'wos', 'ugc_care', 'other']::text[]",
            name=f"ck_{T}_indexing",
        ),
        sa.CheckConstraint("pub_year BETWEEN 1950 AND 2100", name=f"ck_{T}_year"),
        sa.CheckConstraint(
            "verification IN ('waiting', 'returned', 'verified')", name=f"ck_{T}_verification"
        ),
        sa.CheckConstraint(
            "(verification = 'waiting' AND checked_at IS NULL)"
            " OR (verification = 'verified' AND checked_at IS NOT NULL)"
            " OR (verification = 'returned' AND checked_at IS NOT NULL AND library_note <> '')",
            name=f"ck_{T}_check",
        ),
        schema="core",
    )
    op.create_index(f"ix_core_{T}_faculty_id", T, ["faculty_id"], schema="core")
    for column in ("title", "venue"):
        op.create_index(
            f"ix_{T}_{column}_trgm",
            T,
            [column],
            schema="core",
            postgresql_using="gin",
            postgresql_ops={column: "gin_trgm_ops"},
        )
    _owners(OWNERS + f", '{T}'")


def downgrade() -> None:
    op.execute(f"DELETE FROM core.files WHERE table_name = '{T}'")
    _owners(OWNERS)
    op.drop_table(T, schema="core")
