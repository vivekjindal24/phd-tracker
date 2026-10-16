# Architecture

> v2 rewrite. The v1 Frappe architecture (bench, DocTypes, workflow engine,
> print formats) is superseded; the Frappe app stays in `phd_tracker/` as a
> frozen reference and is never modified.

## 1. System Overview

PhD Tracker v2 is a cloud-native polyglot monorepo: three small services, one
Postgres database, $0 free-tier hosting. The daily-use layer (meetings,
progress reports, milestones) is the product; UGC compliance paperwork is
generated as a byproduct (PDF exports).

## 2. Services

| Service | Stack | Deploy | Owns |
|---|---|---|---|
| `services/api` | Python/FastAPI | Koyeb (GHCR image) | Postgres schema `core`, auth, RBAC, workflow, search, audit |
| `services/export` | Node/TypeScript | Render (GHCR image) | Nothing — stateless PDF/CSV rendering over the API's `/internal` endpoints |
| `web` | Next.js App Router | Vercel | Nothing — client-only UI |
| Database | Neon Postgres (free tier) | — | the single source of state |

Hard rules (AGENTS.md): the export service holds zero auth/data logic and
reads only via the API with the caller's token forwarded; all business rules
live in the API's `rbac`/`workflow` modules, never in UI or scripts.

## 3. Technology Stack

| Concern | Choice |
|---|---|
| API | FastAPI, async SQLAlchemy 2 + psycopg 3, Alembic migrations |
| Auth | HS256 access JWT (30 min) + DB-backed rotating single-use refresh tokens |
| DB | Neon Postgres — schema `core`, trigram search indexes |
| Export | Express + pdfkit (node:22-slim, `--max-old-space-size=384`) |
| Web | Next.js 16 (App Router, client components behind an auth gate) |
| CI/CD | GitHub Actions: `ci.yml` (tests) → `deploy.yml` (GHCR images); Vercel deploys `web/` itself |

## 4. Architecture Diagram

```
Browser (Vercel web)
   │  Bearer access JWT (memory) + refresh token (localStorage)
   ├────────────────────► services/api (Koyeb) ──► Neon Postgres, schema `core`
   │                          ▲  /internal/*, caller's token forwarded verbatim
   └──── PDF/CSV download ────┘  services/export (Render)
```

## 5. Key Modules (services/api)

- `auth/` — login/refresh/logout, register (admin-only), `/auth/me`. Refresh
  tokens are sha256-hashed rows in `refresh_tokens`; each refresh rotates the
  row (single-use, rotation on every login).
- `rbac.py` — the permission `MATRIX` as data; route-level `require_perm` +
  row-level `scope()`/`get_or_403` (403, never 404 — record existence is not
  leaked). Closes the v1 Frappe gap (a scholar sees only their own records)
  by construction, not by filtering in the UI.
- `workflow.py` — `TRANSITIONS: (state, action) → (roles, new_state)`; the
  single source of APR state. Illegal action/role → 422 `workflow_violation`.
  `approved_on` is stamped on approve; approved reports are immutable for
  every role.
- `crud.py` — shared insert/update/soft-delete/list helpers; every mutation
  writes an `audit_log` row (actor, action, prev/new JSONB snapshots).
- `errors.py` — one envelope everywhere: `{"error": {code, message, details}}`;
  Postgres constraint violations map to named 409s (`duplicate_apr`,
  `duplicate_roll_number`, `duplicate_email`).
- `seed.py` — idempotent `python -m app.seed` (requires `SEED_PASSWORD`):
  admin, 2 supervisors, 3 scholars, records in every workflow state.

## 6. Data Flow — APR approval (the critical chain)

1. Scholar creates the report (draft) — the API enforces ownership and the
   `uq_apr_active` partial unique index (one live APR per scholar/year/period;
   a duplicate → 409 `duplicate_apr`).
2. Scholar clicks Submit → `POST /reports/{id}/submit` → TRANSITIONS
   (draft, submit, {scholar, admin}) → submitted.
3. Supervisor reads the summary, saves `supervisor_comment` (editable only
   while submitted), then Approve (→ approved, `approved_on` set) or Send back
   (→ rejected). The scholar edits draft/rejected reports only; resubmit
   returns rejected → draft.
4. Research office admin downloads the compliance PDF via the export service,
   which fetches `/internal/reports/{id}/export-view` with the admin's token.
5. Every mutation above writes an `audit_log` row — the audit trail IS the
   compliance product.

## 7. Project Structure

```
phd-tracker/
├── AGENTS.md  README.md  docker-compose.yml
├── .github/workflows/     ci.yml (tests), deploy.yml (GHCR images)
├── docs/                  source of truth (this file et al.)
├── services/api/          FastAPI app + alembic/ + tests/
├── services/export/       Express service + src/ + tests/
├── web/                   Next.js app (src/app, src/lib)
└── phd_tracker/           Frappe v1 app — FROZEN reference, never modify
```

## 8. Deployment

- GH Actions builds `ghcr.io/<owner>/phd-tracker-api` and `…-export` on push
  to main; Koyeb and Render auto-deploy from those images.
- The API runs `alembic upgrade head` before serving (single replica; move to
  a deploy step if replicas ever exceed one).
- All config arrives by environment and is validated loudly at startup
  (`app/config.py`). Never secrets in the repo; never `.env` committed.
- Services are stateless and idle-spin-down tolerant: expect a 15–60s cold
  start; no keep-alive pinger (it burns the free tier's instance hours).

## 9. Failure Scenarios

- **Neon suspended/idle:** API returns 5xx; no data loss (transactions are
  atomic). `pool_pre_ping` drops dead connections before handing them out.
- **Export service down:** the web's export buttons surface the error
  envelope; every daily-use flow is unaffected — it never touches the export
  path.
- **Cold start (Render ~15-min spin-down):** first request is slow; accepted
  per the v2 plan.
- **Migration-on-boot clash:** impossible at one replica; the Dockerfile CMD
  carries the note to move migration into a deploy step if that ever changes.

## 10. Key Technical Decisions (v2 deltas)

| Decision | Reason |
|---|---|
| Three tiny services over a Frappe bench | $0 cloud hosting; no server to run; the buyer (registrar/dean) never logs in — PDFs only |
| JWT + rotating refresh over server sessions | stateless API; works across Koyeb/Render/Vercel with no session store |
| Workflow as a dict, not an engine | four transitions; an engine would be the over-engineering the v1 already paid for |
| Postgres CHECK constraints + partial unique index | duplicate-APR and UGC designation caps enforced by the DB, not hopeful app code |
| Trigram search over a search engine | one DB, no extra service; covers name/roll-number/summary lookups at department scale |
| Access token in memory, refresh in localStorage | XSS-theft risk judged low for a closed tool; upgrade path documented in SECURITY.md |