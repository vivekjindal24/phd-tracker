"""seminar kinds (progress, registration, pre-synopsis), each marked by rubric or form questions

Revision ID: 0038
Revises: 0037
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
# A frozen copy of enums.DEFAULT_SEMINAR_FORMS as of this revision.
DEFAULT_FORMS = {
    "progress": {"marking": "rubric", "form_name": "", "questions": []},
    "registration": {
        "marking": "questions",
        "form_name": "Registration seminar report",
        "questions": [
            "Is the research problem clearly formulated?",
            "Is the review of literature adequate?",
            "Are the objectives clearly stated?",
            "Is the proposed methodology appropriate?",
            "Can the work be completed within the time allowed?",
        ],
    },
    "pre_synopsis": {
        "marking": "questions",
        "form_name": "Pre-synopsis seminar report",
        "questions": [
            "Have the objectives of the research been met?",
            "Are the results adequate for a thesis?",
            "Does the scholar meet the publication requirement?",
            "Is the synopsis in the prescribed format?",
            "Have earlier comments of the committee been addressed?",
        ],
    },
}


def upgrade() -> None:
    op.add_column(
        "seminars",
        sa.Column("kind", sa.Text(), server_default=sa.text("'progress'"), nullable=False),
        schema="core",
    )
    for column in ("report_due", "report_year", "period"):
        op.alter_column("seminars", column, nullable=True, schema="core")
    op.create_check_constraint(
        "ck_seminars_kind",
        "seminars",
        "kind IN ('progress', 'registration', 'pre_synopsis')",
        schema="core",
    )
    op.create_check_constraint(
        "ck_seminars_report",
        "seminars",
        "(kind = 'progress') = (report_due IS NOT NULL AND report_year IS NOT NULL "
        "AND period IS NOT NULL)",
        schema="core",
    )
    op.add_column(
        "settings",
        sa.Column(
            "seminar_forms",
            JSONB,
            server_default=sa.text(f"'{json.dumps(DEFAULT_FORMS)}'::jsonb"),
            nullable=False,
        ),
        schema="core",
    )
    op.create_check_constraint(
        "ck_settings_seminar_forms",
        "settings",
        "jsonb_typeof(seminar_forms) = 'object'",
        schema="core",
    )
    op.add_column("seminar_grades", sa.Column("answers", JSONB), schema="core")
    op.add_column("seminar_grades", sa.Column("recommendation", sa.Text()), schema="core")
    op.create_check_constraint(
        "ck_seminar_grades_recommendation",
        "seminar_grades",
        "recommendation IS NULL OR recommendation IN "
        "('recommended', 'recommended_with_changes', 'not_recommended')",
        schema="core",
    )
    op.create_check_constraint(
        "ck_seminar_grades_form",
        "seminar_grades",
        "(answers IS NULL) = (recommendation IS NULL)",
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("seminar_grades", "recommendation", schema="core")
    op.drop_column("seminar_grades", "answers", schema="core")
    op.drop_column("settings", "seminar_forms", schema="core")
    op.drop_constraint("ck_seminars_report", "seminars", schema="core", type_="check")
    op.drop_constraint("ck_seminars_kind", "seminars", schema="core", type_="check")
    # Fails while registration or pre-synopsis seminars exist: rows are never deleted.
    for column in ("report_due", "report_year", "period"):
        op.alter_column("seminars", column, nullable=False, schema="core")
    op.drop_column("seminars", "kind", schema="core")
