"""faculty requests

Revision ID: 0020
Revises: 0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "faculty_requests",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("seminar_id", sa.UUID(), nullable=True),
        sa.Column("scholar_id", sa.UUID(), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("faculty_id", sa.UUID(), nullable=True),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("note", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('seminar_panel', 'co_supervisor')", name="ck_faculty_req_kind"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'cancelled')",
            name="ck_faculty_req_status",
        ),
        sa.CheckConstraint(
            "(kind = 'seminar_panel' AND seminar_id IS NOT NULL AND scholar_id IS NULL)"
            " OR (kind = 'co_supervisor' AND scholar_id IS NOT NULL AND seminar_id IS NULL)",
            name="ck_faculty_req_target",
        ),
        sa.ForeignKeyConstraint(["faculty_id"], ["core.faculty.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["core.users.id"]),
        sa.ForeignKeyConstraint(["scholar_id"], ["core.scholars.id"]),
        sa.ForeignKeyConstraint(["seminar_id"], ["core.seminars.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="core",
    )
    op.create_index("ix_faculty_requests_email", "faculty_requests", ["email"], schema="core")
    for column in ("faculty_id", "requested_by", "scholar_id", "seminar_id"):
        op.create_index(
            f"ix_core_faculty_requests_{column}", "faculty_requests", [column], schema="core"
        )


def downgrade() -> None:
    op.drop_table("faculty_requests", schema="core")
