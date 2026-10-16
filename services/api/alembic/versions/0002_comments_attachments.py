"""comments + attachments: polymorphic per-record threads and file bytes (bytea)

Revision ID: 0002_comments_attachments
Revises: 0001_initial
Create Date: 2026-10-16
"""

from alembic import op

revision = "0002_comments_attachments"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

STATEMENTS = [
	# comments — record_id has no FK, same polymorphic choice as core.audit_log
	"""
	CREATE TABLE core.comments (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		table_name text NOT NULL CHECK (table_name IN
			('scholars', 'meetings', 'progress_reports', 'milestones')),
		record_id uuid NOT NULL,
		author_id uuid NOT NULL REFERENCES core.users(id),
		body text NOT NULL,
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	"CREATE INDEX ix_comments_record ON core.comments (table_name, record_id)",
	# attachments — bytes in Postgres: Render disk is ephemeral, Neon is the store
	"""
	CREATE TABLE core.attachments (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		table_name text NOT NULL CHECK (table_name IN
			('scholars', 'meetings', 'progress_reports', 'milestones')),
		record_id uuid NOT NULL,
		file_name text NOT NULL,
		content_type text NOT NULL,
		size_bytes int NOT NULL CHECK (size_bytes <= 2097152),
		content bytea NOT NULL,
		uploaded_by uuid NOT NULL REFERENCES core.users(id),
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	"CREATE INDEX ix_attachments_record ON core.attachments (table_name, record_id)",
]


def upgrade() -> None:
	for stmt in STATEMENTS:
		op.execute(stmt)


def downgrade() -> None:
	# Real downgrade for this revision's scope only; 0001's schema-cascade is untouched.
	op.execute("DROP TABLE core.attachments")
	op.execute("DROP TABLE core.comments")