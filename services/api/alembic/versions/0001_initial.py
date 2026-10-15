"""initial schema: core tables, checks, partial-unique APR index, trigram search indexes

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-12
"""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

STATEMENTS = [
	"CREATE EXTENSION IF NOT EXISTS pg_trgm",
	"CREATE EXTENSION IF NOT EXISTS citext",
	"CREATE SCHEMA IF NOT EXISTS core",
	# users
	"""
	CREATE TABLE core.users (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		email citext UNIQUE NOT NULL,
		password_hash text NOT NULL,
		full_name text NOT NULL,
		role text NOT NULL CHECK (role IN ('scholar', 'supervisor', 'admin')),
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	# supervisors
	"""
	CREATE TABLE core.supervisors (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		user_id uuid UNIQUE REFERENCES core.users(id),
		full_name text NOT NULL,
		email citext NOT NULL,
		department text NOT NULL,
		designation text NOT NULL CHECK (designation IN ('Professor', 'Associate Professor', 'Assistant Professor')),
		max_scholars int NOT NULL DEFAULT 8,
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	# scholars
	"""
	CREATE TABLE core.scholars (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		user_id uuid UNIQUE REFERENCES core.users(id),
		scholar_name text NOT NULL,
		roll_number text NOT NULL UNIQUE,
		scholar_email citext,
		department text NOT NULL,
		admission_date date NOT NULL,
		stage text NOT NULL DEFAULT 'Registered' CHECK (stage IN
			('Registered', 'Coursework', 'Proposal Approved', 'Research Phase',
			 'Pre-Synopsis Done', 'Thesis Submitted', 'Viva Voce', 'Degree Awarded')),
		github_url text,
		supervisor_id uuid REFERENCES core.supervisors(id),
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	"CREATE INDEX ix_scholars_supervisor ON core.scholars (supervisor_id)",
	# meetings
	"""
	CREATE TABLE core.meetings (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		scholar_id uuid NOT NULL REFERENCES core.scholars(id),
		supervisor_id uuid NOT NULL REFERENCES core.supervisors(id),
		meeting_date date NOT NULL,
		agenda text,
		minutes text,
		action_items text,
		next_meeting_date date,
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	"CREATE INDEX ix_meetings_scholar ON core.meetings (scholar_id)",
	"CREATE INDEX ix_meetings_supervisor ON core.meetings (supervisor_id)",
	# progress reports (APR)
	"""
	CREATE TABLE core.progress_reports (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		scholar_id uuid NOT NULL REFERENCES core.scholars(id),
		report_year int NOT NULL CHECK (report_year BETWEEN 2000 AND 2100),
		period text NOT NULL CHECK (period IN ('January-June', 'July-December')),
		summary text NOT NULL,
		supervisor_comment text,
		approved_on date,
		state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'submitted', 'approved', 'rejected')),
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	# duplicate-APR block: unique among live rows only
	"""
	CREATE UNIQUE INDEX uq_apr_active ON core.progress_reports (scholar_id, report_year, period)
		WHERE deleted_at IS NULL
	""",
	"CREATE INDEX ix_reports_scholar ON core.progress_reports (scholar_id)",
	# milestones
	"""
	CREATE TABLE core.milestones (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		scholar_id uuid NOT NULL REFERENCES core.scholars(id),
		milestone_type text NOT NULL CHECK (milestone_type IN
			('Coursework Completion', 'Proposal Approval (RDC)', 'Pre-Synopsis Seminar',
			 'Thesis Submission', 'Viva Voce', 'Degree Awarded')),
		status text NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rejected')),
		approval_body text,
		resolution_number text,
		resolution_date date,
		notes text,
		created_at timestamptz NOT NULL DEFAULT now(),
		updated_at timestamptz NOT NULL DEFAULT now(),
		deleted_at timestamptz
	)
	""",
	"CREATE INDEX ix_milestones_scholar ON core.milestones (scholar_id)",
	# audit trail: one table, full snapshots, states per transition
	"""
	CREATE TABLE core.audit_log (
		id bigserial PRIMARY KEY,
		table_name text NOT NULL,
		record_id uuid NOT NULL,
		action text NOT NULL CHECK (action IN ('insert', 'update', 'soft_delete', 'restore', 'transition')),
		from_state text,
		to_state text,
		prev jsonb,
		data jsonb,
		actor_id uuid REFERENCES core.users(id),
		actor_role text NOT NULL,
		at timestamptz NOT NULL DEFAULT now()
	)
	""",
	"CREATE INDEX ix_audit_record ON core.audit_log (table_name, record_id)",
	# refresh tokens
	"""
	CREATE TABLE core.refresh_tokens (
		id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
		user_id uuid NOT NULL REFERENCES core.users(id),
		token_hash text NOT NULL,
		expires_at timestamptz NOT NULL,
		revoked_at timestamptz
	)
	""",
	"CREATE INDEX ix_refresh_user ON core.refresh_tokens (user_id)",
	# search: trigram GIN indexes (partial-match friendly, e.g. 'PHD-CS-2024')
	"CREATE INDEX trgm_scholar_name ON core.scholars USING gin (scholar_name gin_trgm_ops)",
	"CREATE INDEX trgm_roll ON core.scholars USING gin (roll_number gin_trgm_ops)",
	"CREATE INDEX trgm_super_name ON core.supervisors USING gin (full_name gin_trgm_ops)",
	"CREATE INDEX trgm_summary ON core.progress_reports USING gin (summary gin_trgm_ops)",
	"CREATE INDEX trgm_agenda ON core.meetings USING gin (agenda gin_trgm_ops)",
	"CREATE INDEX trgm_ms_type ON core.milestones USING gin (milestone_type gin_trgm_ops)",
	"CREATE INDEX trgm_res_no ON core.milestones USING gin (resolution_number gin_trgm_ops)",
]


def upgrade() -> None:
	for stmt in STATEMENTS:
		op.execute(stmt)


def downgrade() -> None:
	op.execute("DROP SCHEMA core CASCADE")  # extensions stay: shared database objects