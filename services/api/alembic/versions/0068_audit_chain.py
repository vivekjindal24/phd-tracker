"""the audit trail becomes tamper-evident: append-only, and each entry sealed with an HMAC over
its contents and the previous entry's seal (SECURITY.md §6)

The key (AUDIT_KEY) is never stored in the database: each connection sets it (db.py), so
someone who can only reach the database cannot re-seal an entry they changed. Postgres seals
on insert (trigger audit_chain) and checks the whole chain (audit_check()).

Revision ID: 0068
Revises: 0067
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.config import settings

revision: str = "0068"
down_revision: str | None = "0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = """
CREATE FUNCTION core.audit_key() RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE k text := current_setting('anveshan.audit_key', true);
BEGIN
  IF coalesce(k, '') = '' THEN
    RAISE EXCEPTION 'audit_log: the audit key is not set on this connection (AUDIT_KEY)';
  END IF;
  RETURN k;
END $$;

-- An entry's seal: HMAC-SHA256 over the previous seal and the entry's contents. jsonb's text
-- form is canonical, and the time goes in as epoch seconds, so no session setting changes it.
CREATE FUNCTION core.audit_seal(prev_hash text, r core.audit_log) RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT encode(public.hmac(
    coalesce(prev_hash, '') || '|' || jsonb_build_array(
      r.seq, r.id, r.table_name, r.record_id, r.action, r.from_state, r.to_state,
      r.prev, r.data, r.actor_id, r.actor_roles, extract(epoch FROM r.at)
    )::text,
    core.audit_key(), 'sha256'), 'hex')
$$;

-- ponytail: one lock serialises audit inserts until their transaction commits, so seq follows
-- commit order. Fine at a university's write rate; shard the chain per day if it ever is not.
CREATE FUNCTION core.audit_chain() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last core.audit_log;
BEGIN
  PERFORM pg_advisory_xact_lock(4242002);
  SELECT * INTO last FROM core.audit_log ORDER BY seq DESC LIMIT 1;
  NEW.seq := coalesce(last.seq, 0) + 1;
  NEW.hash := core.audit_seal(last.hash, NEW);
  RETURN NEW;
END $$;

CREATE FUNCTION core.audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only: entries are never changed or removed';
END $$;

-- The whole chain, oldest first: how many entries hold, the first that does not (null when
-- all do) and the newest seal. A changed entry fails its own seal; a removed one leaves a gap.
CREATE FUNCTION core.audit_check(OUT entries bigint, OUT broken_at bigint, OUT head text)
LANGUAGE plpgsql STABLE AS $$
DECLARE r core.audit_log;
BEGIN
  entries := 0;
  FOR r IN SELECT * FROM core.audit_log ORDER BY seq LOOP
    IF r.seq <> entries + 1 OR r.hash IS DISTINCT FROM core.audit_seal(head, r) THEN
      broken_at := r.seq;
      RETURN;
    END IF;
    entries := r.seq;
    head := r.hash;
  END LOOP;
END $$;
"""

# Entries written before this migration, sealed in the order they were written.
BACKFILL = """
DO $$
DECLARE r record; last_seal text; n bigint := 0;
BEGIN
  FOR r IN SELECT id FROM core.audit_log ORDER BY at, id LOOP
    n := n + 1;
    UPDATE core.audit_log SET seq = n WHERE id = r.id;
    UPDATE core.audit_log a SET hash = core.audit_seal(last_seal, a) WHERE a.id = r.id
      RETURNING a.hash INTO last_seal;
  END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA public")
    op.add_column("audit_log", sa.Column("seq", sa.BigInteger()), schema="core")
    op.add_column("audit_log", sa.Column("hash", sa.Text()), schema="core")
    op.execute(FUNCTIONS)
    op.execute(
        sa.text("SELECT set_config('anveshan.audit_key', :key, false)").bindparams(
            key=settings.audit_key
        )
    )
    op.execute(BACKFILL)
    op.alter_column("audit_log", "seq", nullable=False, schema="core")
    op.alter_column("audit_log", "hash", nullable=False, schema="core")
    op.create_unique_constraint("uq_audit_log_seq", "audit_log", ["seq"], schema="core")
    op.execute(
        "CREATE TRIGGER audit_chain BEFORE INSERT ON core.audit_log "
        "FOR EACH ROW EXECUTE FUNCTION core.audit_chain()"
    )
    op.execute(
        "CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON core.audit_log "
        "FOR EACH ROW EXECUTE FUNCTION core.audit_append_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_append_only ON core.audit_log")
    op.execute("DROP TRIGGER audit_chain ON core.audit_log")
    for fn in ("audit_check()", "audit_append_only()", "audit_chain()"):
        op.execute(f"DROP FUNCTION core.{fn}")
    op.execute("DROP FUNCTION core.audit_seal(text, core.audit_log)")
    op.execute("DROP FUNCTION core.audit_key()")
    op.drop_constraint("uq_audit_log_seq", "audit_log", schema="core")
    op.drop_column("audit_log", "hash", schema="core")
    op.drop_column("audit_log", "seq", schema="core")
