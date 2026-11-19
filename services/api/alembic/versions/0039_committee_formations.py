"""advisory committee formations: each version dated, members with roles (PRD F9b)

Revision ID: 0039
Revises: 0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
LIVE = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.create_table(
        "committee_formations",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("formed_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.Text()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("secretary_id", UUID, sa.ForeignKey("core.faculty.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        schema="core",
    )
    op.create_index(
        "ix_committee_formations_scholar_id",
        "committee_formations",
        ["scholar_id"],
        schema="core",
    )
    op.add_column(
        "committee_members",
        sa.Column("formation_id", UUID, sa.ForeignKey("core.committee_formations.id")),
        schema="core",
    )
    op.add_column(
        "committee_members",
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'member'")),
        schema="core",
    )
    # Each scholar's existing list becomes one formation, dated by its first live member, with
    # today's supervisor as secretary; it is withdrawn if every member was already removed.
    op.execute(
        """
        INSERT INTO core.committee_formations (scholar_id, formed_on, secretary_id, deleted_at)
        SELECT m.scholar_id,
               coalesce(min(m.created_at) FILTER (WHERE m.deleted_at IS NULL),
                        min(m.created_at))::date,
               s.supervisor_id,
               CASE WHEN bool_or(m.deleted_at IS NULL) THEN NULL ELSE now() END
        FROM core.committee_members m JOIN core.scholars s ON s.id = m.scholar_id
        GROUP BY m.scholar_id, s.supervisor_id
        """
    )
    op.execute(
        """
        UPDATE core.committee_members m SET formation_id = f.id
        FROM core.committee_formations f WHERE f.scholar_id = m.scholar_id
        """
    )
    op.alter_column("committee_members", "formation_id", nullable=False, schema="core")
    op.create_index(
        "ix_committee_members_formation_id", "committee_members", ["formation_id"], schema="core"
    )
    op.create_check_constraint(
        "ck_committee_member_role",
        "committee_members",
        "role IN ('chairperson', 'member', 'vc_nominee')",
        schema="core",
    )
    op.drop_index("uq_committee_member", "committee_members", schema="core")
    op.create_index(
        "uq_committee_member",
        "committee_members",
        ["formation_id", "faculty_id"],
        unique=True,
        postgresql_where=LIVE,
        schema="core",
    )
    op.create_index(
        "uq_committee_chair",
        "committee_members",
        ["formation_id"],
        unique=True,
        postgresql_where=sa.text("role = 'chairperson' AND deleted_at IS NULL"),
        schema="core",
    )


def downgrade() -> None:
    # Back to one list per scholar: members of earlier formations are withdrawn (soft-deleted).
    op.execute(
        """
        UPDATE core.committee_members m SET deleted_at = now()
        WHERE m.deleted_at IS NULL AND m.formation_id <> (
            SELECT f.id FROM core.committee_formations f
            WHERE f.scholar_id = m.scholar_id AND f.deleted_at IS NULL
            ORDER BY f.formed_on DESC, f.created_at DESC LIMIT 1)
        """
    )
    op.drop_index("uq_committee_chair", "committee_members", schema="core")
    op.drop_index("uq_committee_member", "committee_members", schema="core")
    op.create_index(
        "uq_committee_member",
        "committee_members",
        ["scholar_id", "faculty_id"],
        unique=True,
        postgresql_where=LIVE,
        schema="core",
    )
    op.drop_constraint("ck_committee_member_role", "committee_members", schema="core")
    op.drop_index("ix_committee_members_formation_id", "committee_members", schema="core")
    op.drop_column("committee_members", "role", schema="core")
    op.drop_column("committee_members", "formation_id", schema="core")
    op.drop_index("ix_committee_formations_scholar_id", "committee_formations", schema="core")
    op.drop_table("committee_formations", schema="core")
