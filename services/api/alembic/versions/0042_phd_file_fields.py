"""the PhD file's small records: supervisor appointments kept as history, father's name,
examiner origin, the comprehensive examination, the assistantship line, named file slots

Revision ID: 0042
Revises: 0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
NOW = sa.text("now()")
ORIGIN = "origin IN ('national', 'international')"


def _appointments() -> None:
    op.create_table(
        "supervisor_appointments",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("faculty_id", UUID, sa.ForeignKey("core.faculty.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("appointed_on", sa.Date()),
        sa.Column("order_ref", sa.Text()),
        sa.Column("ended_on", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "role IN ('supervisor', 'co_supervisor')", name="ck_supervisor_appointments_role"
        ),
        sa.CheckConstraint(
            "ended_on IS NULL OR appointed_on IS NULL OR ended_on >= appointed_on",
            name="ck_supervisor_appointments_dates",
        ),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_supervisor_appointments_scholar_id"),
        "supervisor_appointments",
        ["scholar_id"],
        schema="core",
    )
    op.create_index(
        "uq_supervisor_appointment_open",
        "supervisor_appointments",
        ["scholar_id", "role"],
        unique=True,
        postgresql_where=sa.text("ended_on IS NULL AND deleted_at IS NULL"),
        schema="core",
    )
    # Today's supervisors become open appointments; when and by which order is for the admin.
    for role, column in (("supervisor", "supervisor_id"), ("co_supervisor", "co_supervisor_id")):
        op.execute(
            "INSERT INTO core.supervisor_appointments (scholar_id, faculty_id, role) "
            f"SELECT id, {column}, '{role}' FROM core.scholars "
            f"WHERE {column} IS NOT NULL AND deleted_at IS NULL"
        )


def upgrade() -> None:
    _appointments()
    op.add_column("scholars", sa.Column("father_name", sa.Text()), schema="core")
    for table, check in (
        ("examiner_reports", "ck_examiner_reports_origin"),
        ("thesis_reviews", "ck_thesis_reviews_origin"),
    ):
        op.add_column(table, sa.Column("origin", sa.Text()), schema="core")
        op.create_check_constraint(check, table, ORIGIN, schema="core")
    op.add_column("progress_reports", sa.Column("assistantship", sa.Text()), schema="core")
    op.create_check_constraint(
        "ck_apr_assistantship",
        "progress_reports",
        "assistantship IN ('with', 'without')",
        schema="core",
    )
    op.add_column("files", sa.Column("slot", sa.Text()), schema="core")
    op.create_check_constraint(
        "ck_files_slot",
        "files",
        "slot IS NULL OR (table_name = 'scholars'"
        " AND slot IN ('employer_noc', 'entrance_minutes'))",
        schema="core",
    )
    op.create_table(
        "comprehensive_exams",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("scholar_id", UUID, sa.ForeignKey("core.scholars.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("held_in", sa.Date(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("attempt >= 1", name="ck_comprehensive_attempt"),
        sa.CheckConstraint("extract(day FROM held_in) = 1", name="ck_comprehensive_month"),
        sa.CheckConstraint(
            "result IN ('satisfactory', 'unsatisfactory')", name="ck_comprehensive_result"
        ),
        schema="core",
    )
    op.create_index(
        op.f("ix_core_comprehensive_exams_scholar_id"),
        "comprehensive_exams",
        ["scholar_id"],
        schema="core",
    )
    op.create_index(
        "uq_comprehensive_attempt",
        "comprehensive_exams",
        ["scholar_id", "attempt"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("comprehensive_exams", schema="core")
    op.drop_constraint("ck_files_slot", "files", schema="core")
    op.drop_column("files", "slot", schema="core")
    op.drop_constraint("ck_apr_assistantship", "progress_reports", schema="core")
    op.drop_column("progress_reports", "assistantship", schema="core")
    for table, check in (
        ("examiner_reports", "ck_examiner_reports_origin"),
        ("thesis_reviews", "ck_thesis_reviews_origin"),
    ):
        op.drop_constraint(check, table, schema="core")
        op.drop_column(table, "origin", schema="core")
    op.drop_column("scholars", "father_name", schema="core")
    op.drop_table("supervisor_appointments", schema="core")
