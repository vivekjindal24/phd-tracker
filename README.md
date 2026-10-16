# PhD Tracker

Supervisor–scholar workspace for Indian university PhD programs. The daily-use
layer (meetings, progress reports, milestone approvals) is the product; UGC
compliance paperwork (UGC 2022 PhD Regulations, as amended March 2024) falls
out as a byproduct.

Status: **v2 — deployed.** Live at
`https://phd-tracker-vivekjindal24s-projects.vercel.app` (web),
`https://phd-tracker-api.onrender.com` (API), `https://phd-tracker-export.onrender.com`
(export), on Neon Postgres. The Frappe v1 app (`phd_tracker/`) stays in-repo as a
frozen reference until deleted per the roadmap; it is never modified.

## Architecture (v2)

Three codebases, deliberately not one framework, everything on free-tier cloud:

```
web (Next.js, Vercel)  ──►  services/api (FastAPI, Render)  ──►  Neon Postgres
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
API_URL=http://localhost:8000/api/v1 npm run dev   # :8100

# Web
cd web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8900/api/v1 \
NEXT_PUBLIC_EXPORT_URL=http://localhost:8902 \
npm run dev                 # :3000
```

Or `docker compose up` (Postgres + API on :8900 + export on :8902); set
`JWT_SECRET` in a gitignored `.env` beside the compose file. The three-role
click-through checklist lives in `docs/TESTING.md`.

## CI/CD

GitHub Actions: `ci.yml` (ruff + pytest against a Postgres service container;
typecheck + node:test; web build) runs on every push/PR. On `main`, `deploy.yml`
builds `ghcr.io/<owner>/phd-tracker-api` and `…-export` and pushes them to GHCR.
Render image-backed services do NOT auto-pull updated tags — after a deploy.yml
run, trigger **Manual Deploy → Deploy latest** on each Render service (or wire
its Settings → *Deploy Hook* URL into the pipeline). Vercel deploys `web/` itself.
`keepalive.yml` pings both healthz endpoints every 5 min so the free-tier
services never spin down (a 20s cold start otherwise greets the first user
after 15 idle minutes).

## Environment variables (never in repo)

| Service | Vars |
|---|---|
| api | `DATABASE_URL` (Neon pooled string), `JWT_SECRET` (≥32 bytes), `CORS_ORIGINS` (the Vercel web origin) |
| export | `API_URL`, `PORT`, `CORS_ORIGINS` (the Vercel web origin) |
| web | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_EXPORT_URL` |

## Deployment runbook (free tiers)

1. **Neon**: create project → copy the pooled connection string.
2. **GHCR**: push to `main` — `deploy.yml` publishes both images.
3. **Render** (API): New → Web Service → existing image, deploy
   `ghcr.io/<owner>/phd-tracker-api:latest`; set `DATABASE_URL`, `JWT_SECRET`,
   `PORT=8000`, `CORS_ORIGINS=https://<app>.vercel.app`.
   The container runs `alembic upgrade head` before serving.
4. **Render** (export): same project, second web service from
   `ghcr.io/<owner>/phd-tracker-export:latest`; set `API_URL` (the API URL +
   `/api/v1`), `PORT=8100`, `CORS_ORIGINS` as above. Both free services
   spin down after ~15 min idle.
5. **Vercel** (web): import the repo, root directory `web/`, set the two
   `NEXT_PUBLIC_*` vars to the Render URLs.
6. **Seed production once**: `DATABASE_URL='<neon>' SEED_PASSWORD='<one-time>' \
   python -m app.seed` (idempotent; rotate the password on first login).
7. Click through `docs/TESTING.md` against the deployed URLs; a first-request
   cold start of 15–60s is expected on both Render services.

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