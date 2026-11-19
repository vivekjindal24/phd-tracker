"""department research committees: formations owned by a unit, members with a seat (PRD F9b)

Revision ID: 0040
Revises: 0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
LIVE = sa.text("deleted_at IS NULL")
TWO_KINDS = (
    "(faculty_id IS NOT NULL AND name IS NULL AND institution IS NULL)"
    " OR (faculty_id IS NULL AND name IS NOT NULL AND institution IS NOT NULL)"
)
THREE_KINDS = (
    "(faculty_id IS NOT NULL AND scholar_member_id IS NULL"
    " AND name IS NULL AND institution IS NULL)"
    " OR (scholar_member_id IS NOT NULL AND faculty_id IS NULL"
    " AND name IS NULL AND institution IS NULL)"
    " OR (faculty_id IS NULL AND scholar_member_id IS NULL"
    " AND name IS NOT NULL AND institution IS NOT NULL)"
)


RENAMED = (  # 0039 named these off the ix_core_<table>_<column> convention
    ("ix_committee_formations_scholar_id", "ix_core_committee_formations_scholar_id"),
    ("ix_committee_members_formation_id", "ix_core_committee_members_formation_id"),
)


def upgrade() -> None:
    for old, new in RENAMED:
        op.execute(f"ALTER INDEX core.{old} RENAME TO {new}")
    # A formation belongs to a scholar (advisory committee) or a unit (department committee).
    op.alter_column("committee_formations", "scholar_id", nullable=True, schema="core")
    op.add_column(
        "committee_formations",
        sa.Column("unit_id", UUID, sa.ForeignKey("core.org_units.id")),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_committee_formations_unit_id"),
        "committee_formations",
        ["unit_id"],
        schema="core",
    )
    op.create_check_constraint(
        "ck_committee_formation_owner",
        "committee_formations",
        "(scholar_id IS NULL) <> (unit_id IS NULL)",
        schema="core",
    )
    # Members: whose committee is read from the formation; a scholar may sit on one.
    op.drop_index("ix_core_committee_members_scholar_id", "committee_members", schema="core")
    op.drop_column("committee_members", "scholar_id", schema="core")
    op.add_column(
        "committee_members",
        sa.Column("scholar_member_id", UUID, sa.ForeignKey("core.scholars.id")),
        schema="core",
    )
    op.add_column("committee_members", sa.Column("seat", sa.Text()), schema="core")
    op.drop_constraint("ck_committee_member_kind", "committee_members", schema="core")
    op.create_check_constraint(
        "ck_committee_member_kind", "committee_members", THREE_KINDS, schema="core"
    )
    op.drop_constraint("ck_committee_member_role", "committee_members", schema="core")
    op.create_check_constraint(
        "ck_committee_member_role",
        "committee_members",
        "role IN ('chairperson', 'secretary', 'member', 'vc_nominee')",
        schema="core",
    )
    op.create_check_constraint(
        "ck_committee_member_seat",
        "committee_members",
        "seat IN ('hod', 'dean_nominee', 'faculty_nominee', 'vc_nominee', 'scholar')",
        schema="core",
    )
    op.create_index(
        "uq_committee_scholar_member",
        "committee_members",
        ["formation_id", "scholar_member_id"],
        unique=True,
        postgresql_where=LIVE,
        schema="core",
    )
    op.create_index(
        "uq_committee_secretary",
        "committee_members",
        ["formation_id"],
        unique=True,
        postgresql_where=sa.text("role = 'secretary' AND deleted_at IS NULL"),
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column(
            "department_committee_name",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Department Research Committee (DRC)'"),
        ),
        schema="core",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text("SELECT count(*) FROM core.committee_formations WHERE unit_id IS NOT NULL")
    ):
        raise RuntimeError(
            "department committees are recorded; revision 0039 cannot hold them — "
            "export and remove them first"
        )
    op.drop_column("settings", "department_committee_name", schema="core")
    op.drop_index("uq_committee_secretary", "committee_members", schema="core")
    op.drop_index("uq_committee_scholar_member", "committee_members", schema="core")
    op.drop_constraint("ck_committee_member_seat", "committee_members", schema="core")
    op.drop_constraint("ck_committee_member_role", "committee_members", schema="core")
    op.create_check_constraint(
        "ck_committee_member_role",
        "committee_members",
        "role IN ('chairperson', 'member', 'vc_nominee')",
        schema="core",
    )
    op.drop_constraint("ck_committee_member_kind", "committee_members", schema="core")
    op.create_check_constraint(
        "ck_committee_member_kind", "committee_members", TWO_KINDS, schema="core"
    )
    op.drop_column("committee_members", "seat", schema="core")
    op.drop_column("committee_members", "scholar_member_id", schema="core")
    op.add_column(
        "committee_members",
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id")),
        schema="core",
    )
    op.execute(
        "UPDATE core.committee_members m SET scholar_id = f.scholar_id"
        " FROM core.committee_formations f WHERE f.id = m.formation_id"
    )
    op.alter_column("committee_members", "scholar_id", nullable=False, schema="core")
    op.create_index(
        op.f("ix_core_committee_members_scholar_id"),
        "committee_members",
        ["scholar_id"],
        schema="core",
    )
    op.drop_constraint("ck_committee_formation_owner", "committee_formations", schema="core")
    op.drop_index("ix_core_committee_formations_unit_id", "committee_formations", schema="core")
    op.drop_column("committee_formations", "unit_id", schema="core")
    op.alter_column("committee_formations", "scholar_id", nullable=False, schema="core")
    for old, new in RENAMED:
        op.execute(f"ALTER INDEX core.{new} RENAME TO {old}")
