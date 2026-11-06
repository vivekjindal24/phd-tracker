"""provisional certificates

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provisional_certificates",
        sa.Column("thesis_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("serial", sa.Text(), nullable=False),
        sa.Column("verify_token", sa.Text(), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoked_reason IS NULL)", name="ck_certificate_revoked"
        ),
        sa.ForeignKeyConstraint(["thesis_id"], ["core.thesis_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "number", name="uq_certificate_serial"),
        sa.UniqueConstraint("verify_token", name="uq_certificate_token"),
        schema="core",
    )
    op.create_index(
        "ix_core_provisional_certificates_thesis_id",
        "provisional_certificates",
        ["thesis_id"],
        schema="core",
    )
    op.create_index(
        "uq_certificate_active",
        "provisional_certificates",
        ["thesis_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("revoked_at IS NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("provisional_certificates", schema="core")
