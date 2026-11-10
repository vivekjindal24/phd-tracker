"""research advisory committee members

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "committee_members",
        sa.Column("scholar_id", sa.UUID(), nullable=False),
        sa.Column("faculty_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("institution", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "(faculty_id IS NOT NULL AND name IS NULL AND institution IS NULL)"
            " OR (faculty_id IS NULL AND name IS NOT NULL AND institution IS NOT NULL)",
            name="ck_committee_member_kind",
        ),
        sa.ForeignKeyConstraint(["scholar_id"], ["core.scholars.id"]),
        sa.ForeignKeyConstraint(["faculty_id"], ["core.faculty.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_committee_members_scholar_id"),
        "committee_members",
        ["scholar_id"],
        schema="core",
    )
    op.create_index(
        "uq_committee_member",
        "committee_members",
        ["scholar_id", "faculty_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("committee_members", schema="core")
