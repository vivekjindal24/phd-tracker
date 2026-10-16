# Database

> v2 rewrite: MariaDB/Frappe DocTypes → Neon Postgres, schema `core`, Alembic
> migrations. The Frappe-era table descriptions are superseded; the
> authoritative DDL is `services/api/alembic/versions/0001_initial.py`.

## 1. Engine & Access

- **Postgres 16** (Neon free tier in production; brew pg15 locally; a GH
  Actions `postgres:16` service container in CI). Extensions: `pg_trgm`
  (search), `citext` (case-insensitive emails).
- Only `services/api` connects to the database. The export service reads via
  the API's `/internal` REST endpoints with the caller's token; the web holds
  no DB access at all.
- Connection string arrives as `DATABASE_URL` (`postgresql+psycopg://…`),
  validated at startup. Pool is small (`pool_size=2, max_overflow=3`) — Neon
  free tier caps connections; `pool_pre_ping` drops dead ones.

## 2. Naming Conventions

- Tables: plural snake_case in schema `core` (`users`, `scholars`,
  `progress_reports`, `audit_log`).
- Columns: snake_case; ids are `uuid` (`gen_random_uuid()`).
- Every row carries `created_at`/`updated_at` (`timestamptz`) and
  `deleted_at` (soft delete marker).
- Enums are `text` + `CHECK` constraints (no Postgres enum types) — values
  mirror the Pydantic Literals exactly, and vice versa.

## 3. Tables

### users
Login identity: `email` (citext, UNIQUE), `password_hash`, `full_name`,
`role` CHECK (`scholar`/`supervisor`/`admin`). The 1:1 profile bindings live
on the profile tables (`scholars.user_id`, `supervisors.user_id`, UNIQUE).

### supervisors
`full_name`, `email` (citext), `department`, `designation` CHECK
(Professor/Associate Professor/Assistant Professor), `max_scholars`
(default 8). UGC designation caps (8/6/4) are enforced in the scholars
router on assignment — over cap → 409 `supervisor_cap_exceeded`.

### scholars
`scholar_name`, `roll_number` (UNIQUE), `scholar_email` (citext),
`department`, `admission_date`, `stage` CHECK (Registered → Degree
Awarded, default Registered), `github_url`, `supervisor_id` FK (indexed).

### meetings
`scholar_id`, `supervisor_id` (both FKs, indexed), `meeting_date`, `agenda`,
`minutes`, `action_items`, `next_meeting_date`.

### progress_reports (the APR)
`scholar_id` (indexed), `report_year` CHECK 2000–2100, `period` CHECK
(January-June/July-December), `summary`, `supervisor_comment`,
`approved_on` (set on approve), `state` CHECK
(draft/submitted/approved/rejected, default draft). APR lifecycle state
lives ONLY in this column, driven by `workflow.py` — never in a client or
ad-hoc field.

### milestones
`scholar_id` (indexed), `milestone_type` CHECK (six UGC lifecycle types),
`status` CHECK (Pending/Approved/Rejected, default Pending),
`approval_body`, `resolution_number`, `resolution_date`, `notes`.

### audit_log
Every mutation on every table writes one row: `table_name`, `record_id`,
`action` CHECK (insert/update/soft_delete/restore/transition),
`from_state`/`to_state` (transitions), `prev`/`data` (JSONB snapshots),
`actor_id` FK, `actor_role`, `at`. This is the compliance product — writes
happen only in `crud.py`/`workflow.py`, never ad-hoc.

### refresh_tokens
`user_id` (indexed), `token_hash` (sha256 of the urlsafe token — raw tokens
are never stored), `expires_at`, `revoked_at`. Single-use: each refresh
rotates (revoke old row + issue new token).

### comments
Flat per-record threads. `(table_name, record_id)` polymorphic pair
(indexed) — same pattern as audit_log: no FK on `record_id` (Postgres can't
express a polymorphic FK), a CHECK whitelist on `table_name`
(scholars/meetings/progress_reports/milestones) substitutes for it.
`author_id` FK users, `body` (1–4000 chars). Visibility is the target
record's `get_or_403` — comments have no MATRIX row and no `scope()`.

### attachments
File bytes in Postgres (`content bytea`) — Render's disk is ephemeral, Neon
is the only persistent store on the free tier. Same polymorphic
`(table_name, record_id)` pair + CHECK whitelist as comments, plus
`file_name`, `content_type`, `size_bytes`, `uploaded_by` FK users.
2MB cap enforced twice: `ck_attachments_size` CHECK and a router check
(fast 413 rejection). List responses are metadata-only (`AttachmentOut`);
bytes are served solely by `GET /attachments/{id}/download`, which applies
the target record's `get_or_403` first. `audit.snapshot()` skips bytea
columns — file bytes never enter the audit JSONB.

## 4. Constraints & Invariants

- **Duplicate APR:** partial unique index
  `uq_apr_active (scholar_id, report_year, period) WHERE deleted_at IS NULL`
  → 409 `duplicate_apr`. One live APR per scholar per period; soft-deleted
  rows excluded.
- **Unique identities:** `scholars.roll_number`, `users.email` — constraint
  violations map to named 409s in `errors.py` (psycopg `.diag.constraint_name`).
- **Referential integrity:** FKs on every link; all writes go through the
  API's crud helpers, which audit before commit.
- **Soft delete only.** `deleted_at` on every domain table; no hard deletes
  by anyone. Every query path filters `deleted_at IS NULL` (`live_and_scoped`).

## 5. Search

Trigram GIN indexes (`pg_trgm`): scholar_name, roll_number, supervisor
full_name, report summary, meeting agenda, milestone_type,
resolution_number. `GET /search?q=` ILIKEs across them, scoped by role —
partial matches like `PHD-CS-2024` work (v1's fulltext tokenizer didn't).

## 6. Migration Rules

Schema changes must:
1. Ship an Alembic migration in the same change (`alembic/versions/`) —
   never raw SQL against a live DB.
2. Update DATABASE.md in the same commit (AGENTS.md §3).
3. Be verified with `alembic upgrade head` against a scratch DB; CI runs the
   full migration chain before every test suite, so a broken migration fails CI.
4. Never break existing records (audit_log and soft-delete history are the
   compliance trail).

## 7. Seed Data

`DATABASE_URL=… SEED_PASSWORD=… python -m app.seed` — idempotent (re-runs
touch nothing). Seeds: admin, 2 supervisors (Dr. Meera Krishnan, Dr. Rajesh
Nair), 3 scholars (Arun Bhatt PHD-CS-2024-001, Priya Sharma, Vikram Rao),
and records covering every workflow state. In production, seed runs once
against Neon after first deploy; the password arrives by env, and the first
thing the research office does is rotate it.

## Legacy notes (Frappe v1 — superseded)

DocType JSON schemas, `tab*` tables, bench patches, and Frappe version
history are frozen in `phd_tracker/` for reference only. Ideas worth porting
when the matching feature is pulled: `research_title` on scholar, document
versioning, notification channels, `google_event_id` on meetings (from the
removed Spring Boot prototype).