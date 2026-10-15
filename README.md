# PhD Tracker

Supervisor–scholar workspace for Indian university PhD programs. The daily-use
layer (meetings, progress reports, milestone approvals) is the product; UGC
compliance paperwork (UGC 2022 PhD Regulations, as amended March 2024) falls
out as a byproduct.

Status: **v2 — cloud-native rewrite in progress.** The original Frappe v1 app
(`phd_tracker/`) stays in-repo as a reference implementation until the v2
stack reaches parity; it is never modified.

## Architecture (v2)

Three codebases, deliberately not one framework, everything on free-tier cloud:

```
web (Next.js, Vercel)  ──►  services/api (FastAPI, Koyeb)  ──►  Neon Postgres
        └──────────────►  services/export (Node/TS, Render) ──┘ (via API /internal, token forwarded)
```

| Service | Stack | Owns |
|---|---|---|
| `services/api` | Python/FastAPI, SQLAlchemy 2 async, Alembic | Auth (JWT + rotating refresh), scholars/supervisors/meetings/reports/milestones, APR workflow state machine, RBAC + ownership, audit log, trigram search |
| `services/export` | Node 22/TypeScript, pdfkit | APR PDF, milestone register PDF/CSV. Stateless; no DB, no auth logic |
| `web` | Next.js App Router | Login, role-gated UI, workflow actions, downloads |

Data model: single `core` schema — soft-delete only, one `audit_log` table
with full row snapshots per change (the compliance trail is the product).
Duplicate APRs per (scholar, year, period) blocked by a partial unique index.

## Local development

Requirements: Homebrew Postgres 15+ (with `pg_trgm`, `citext`), Python 3.12
(venv off the exFAT volume), Node 22.

```bash
# API
createdb phd_tracker_dev
psql -d phd_tracker_dev -c "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS citext;"
cd services/api
uv venv --python 3.12 ~/.venvs/phd-tracker-api
uv pip install -e ".[dev]" --python ~/.venvs/phd-tracker-api/bin/python
export DATABASE_URL="postgresql+psycopg://$(whoami)@localhost/phd_tracker_dev"
alembic upgrade head          # note: exFAT — delete ._* junk first if alembic errors
uvicorn app.main:app --port 8000

# Export
cd services/export
npm install
npm run dev                   # :8100

# Web — added in Phase 3
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`): ruff + pytest against a Postgres
service container (api), typecheck + node:test (export). Images build in CI to
GHCR and deploy via hooks (Koyeb/Render); Vercel deploys `web/` on push.

## Environment variables (never in repo)

| Service | Vars |
|---|---|
| api | `DATABASE_URL` (Neon pooled string), `JWT_SECRET`, `CORS_ORIGINS` |
| export | `API_URL`, `PORT` |
| web | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_EXPORT_URL` |

## Workflow: Progress Report (APR) approval

```
draft --(scholar: submit)--> submitted --(supervisor: approve)--> approved (approved_on set)
                                submitted --(supervisor: send_back)--> rejected
                                rejected --(scholar: resubmit)--> draft
```

Enforced server-side in `services/api/app/workflow.py`; the UI only offers
what the API permits.

## Deliberately NOT in v1

Admissions, coursework grading, grants/ledger, plagiarism-check API
integration (record similarity scores manually for now), NAAC/NIRF exports,
Shodhganga sync, GitHub activity mirroring, VC dashboards, committee logins.
Each waits for a paying university to pull it.

## Roadmap

1. v2 parity with Frappe v1 (then delete `phd_tracker/`)
2. Per-scholar timeline view (meetings + reports + milestones on one page)
3. Read-only GitHub activity mirror (commit streak per scholar)
4. UGC-format export pack once a pilot university supplies formats