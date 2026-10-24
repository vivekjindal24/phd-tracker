# Architecture

> v3 rewrite (2026-10): university-wide scope (org tree, multi-role scoped
> access, configurable approval chains, optional modules), object storage for
> files, and two deployment targets — free cloud for dev/test, self-hosted
> Docker Compose for production. The v1 Frappe app and the v2 code survive
> only in git history (before commit `c6dae35`).

## 1. System Overview

Anveshan is a polyglot monorepo: three small services, one Postgres database,
one S3-compatible bucket. Every piece ships as a Docker image so the same
build runs on free cloud tiers (development, testing, demos) and on a
university's own server/NAS (production).

## 2. Services

| Service | Stack | Owns |
|---|---|---|
| `services/api` | Python/FastAPI | Postgres schema `core`; auth, scope/RBAC, approval engine, modules, notifications, search, audit, file metadata + signed URLs |
| `services/export` | Node/TypeScript | Nothing — stateless PDF/CSV rendering over the API's `/internal` endpoints, caller's token forwarded |
| `web` | Next.js App Router | Nothing — client UI |
| Database | Postgres 16 | the single source of state |
| Object storage | S3-compatible (R2 / Garage) | file bytes only; the API holds metadata and signs URLs |

Hard rules (AGENTS.md): the export service holds zero auth/data logic; all
business rules live in the API's `scope`/`rbac`/`workflow` modules, never in
UI or scripts; file bytes never pass through the export service.

## 3. Technology Stack

| Concern | Choice |
|---|---|
| API | FastAPI, async SQLAlchemy 2 + psycopg 3, Alembic migrations |
| Auth | HS256 access JWT (30 min) + DB-backed rotating single-use refresh tokens |
| DB | Postgres 16 — schema `core`, `ltree` for the org tree, `pg_trgm` search |
| Files | S3 API via `boto3`/`aioboto3`-compatible client; presigned PUT/GET (5 min) |
| Email | SMTP (`aiosmtplib`), sent after commit; failures recorded, never silent |
| Export | Express + pdfkit (node:22-slim) |
| Web | Next.js 16 (App Router, client components behind an auth gate), `output: "standalone"` for self-hosting |
| CI/CD | Render builds `services/api/Dockerfile` and Vercel builds `web/` on every push to the deploy branch; GitHub Actions `ci.yml` (tests) to be added |

## 4. Deployment Targets

| | Dev / test (free cloud) | Production (per university) |
|---|---|---|
| Postgres | Neon (branch per environment) | `postgres:16` container, volume on the NAS |
| API, export | Render free (Docker build from repo, region Ohio = Neon's) | containers built from the same Dockerfiles |
| Web | Vercel | `web` standalone container |
| Files | Cloudflare R2 | Garage container (S3-compatible), volume on the NAS, served at its own `FILES_DOMAIN` through Caddy |
| Email | free SMTP relay | university SMTP |
| TLS / routing | platform default | Caddy reverse proxy (automatic HTTPS) |
| Scheduled jobs | GitHub Actions cron, once daily | cron container: daily job + nightly backup |

The code never branches on the target: everything differs only by
environment variables (§9). In production Caddy serves the app on one origin
(`/api/*` → API, `/export/*` → export, the rest → web) and the file store on
`FILES_DOMAIN`, which inside the compose network resolves to Caddy so the API
and browsers sign and reach the same URL. Garage replaced MinIO (Decided
2026-10-24): MinIO stopped publishing its free server image. The operator's
install, backup and restore steps are in `deploy/README.md`.

**Current dev/test deployment (2026-10):** branch `rewrite` →
web `https://research.vivekjindal.in` (Vercel project `anveshan`, root
`web/`, production branch `rewrite`), API `https://anveshan-api-5xem.onrender.com`
(Render service `anveshan-api`, root `services/api`), export
`https://phd-tracker-ik19.onrender.com` (Render, root `services/export`;
Vercel `NEXT_PUBLIC_EXPORT_URL`), database `anveshan` in the existing Neon
project. Both redeploy on every push to `rewrite`; `main`
still serves v2 until the cut-over merge.

## 5. Architecture Diagram

```
Browser (web)
   │  Bearer access JWT (memory) + refresh token (localStorage)
   ├──────────────► services/api ──► Postgres (schema core)
   │                   │   ▲  /internal/*, caller's token forwarded
   │                   │   └──────── services/export ◄── PDF/CSV download
   │                   └─ signs URLs ─┐
   └──── file PUT/GET (presigned) ────► S3-compatible storage (R2 / Garage)
```

## 6. Key Modules (services/api)

- `auth/` — login/refresh/logout, `/auth/me` (returns the user's role
  assignments and enabled modules). Refresh tokens are sha256-hashed rows,
  rotated on every use. Set-password links (invite / forgot password) in
  `service.py`; university-email login in `sso.py` (OpenID Connect code flow
  + PKCE against Google or Microsoft, id_token verified against the
  provider's JWKS; matches existing accounts only).
- `org.py` — org-unit tree on `ltree` paths; subtree queries are one indexed
  `path <@ :unit_path` predicate.
- `scope.py` — the single place visibility is computed: turns a user's role
  assignments into a SQL predicate per entity (self / supervisees / unit
  subtree / university-wide). Every list, detail, search, dashboard and
  export goes through it. Out-of-scope id → 403, never 404.
- `rbac.py` — `MATRIX`: (role, entity) → allowed actions, as data. Route
  guard `require_perm`; row guard `get_or_403` combines MATRIX + scope.
- `workflow.py` — the **one** approval engine for all four item types.
  States `draft → in_review → approved`, plus `sent_back`. The item stores
  `current_step` and a `chain_snapshot` copied from `approval_chains` at
  submit. `can_act(user, item)` resolves the current step's actor (scholar's
  supervisor / head or admin of the scholar's unit / an office role). Illegal
  action → 422 `workflow_violation`. Approved items are immutable.
- `modules.py` — enabled-module check as a router dependency → 404
  `module_disabled`.
- `notify.py` — writes `notifications` rows in the same transaction as the
  event; emails are sent after commit and their outcome stored on the row.
- `files.py` — file metadata, presigned upload/download after the target
  record's `get_or_403`; size cap from config.
- `duration.py` — the UGC maximum-duration rule as one pure function
  (limit date, status, warnings); `leadership.py` — the at-risk list,
  completion times, drop-outs and supervisor load for a unit subtree;
  `coursework.py` — credits / CGPA against the university minimums.
- `bulk_import.py` + `spreadsheet.py` — Excel/CSV import of faculty,
  scholars and register history (PRD F16): every row checked first (same
  rules as the forms via `directory.create_person` / `assign_supervisor`),
  then one transaction; templates generated with openpyxl.
- `crud.py` — shared insert/update/soft-delete/list helpers; every mutation
  writes an `audit_log` row.
- `errors.py` — one envelope everywhere: `{"error": {code, message,
  details}}`; constraint violations map to named 409s.
- `seed.py` — idempotent demo data: a university tree (University → 2
  Schools → 4 Departments), every role, records in every workflow state.

## 7. Data Flow — an approval chain (publication example)

1. Scholar creates the publication (draft) and attaches the PDF (presigned
   upload; `files` row written by the API).
2. **Submit** → `POST /publications/{id}/submit` → engine copies the
   publication chain into `chain_snapshot`, sets `in_review`, step 0
   (Supervisor). A notification goes to the supervisor.
3. Supervisor **approves** → step 1 (Library); Library users are notified.
4. Library checks indexing and **sends back to step 0** with a comment →
   supervisor notified; or **approves** → step 2 (Research Office).
5. Research Office approves → `approved`, immutable. Scholar notified.
6. Every action writes an `approval_actions` row (actor, step, action,
   comment) and an `audit_log` row — the trail IS the compliance product.

## 8. Project Structure

```
anveshan (repo: phd-tracker)/
├── AGENTS.md  README.md
├── deploy/                   self-hosted stack: compose.prod.yml, Caddyfile, garage.toml,
│                             garage-init.sh, cron/ (daily job + backups), README.md
├── .github/workflows/        ci.yml (tests + fresh-install stack), cron.yml (daily job, cloud)
├── docs/                     source of truth
├── services/api/             FastAPI app + alembic/ + tests/
├── services/export/          Express service + src/ + tests/
└── web/                      Next.js app (src/app, src/components, src/lib)
```

## 9. Configuration

All config arrives by environment and is validated loudly at startup
(`app/config.py`); never secrets in the repo, never `.env` committed.
API: `DATABASE_URL`, `JWT_SECRET` (≥32 bytes), `CORS_ORIGINS`,
`S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`,
`S3_REGION`, `MAX_UPLOAD_MB` (default 100), `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `APP_BASE_URL`, `CRON_SECRET`.
AI (optional, all-or-nothing): `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` — any
OpenAI-compatible chat endpoint (Gemini in dev, Ollama in production); unset =
supervisors write seminar to-do points by hand.
The five SMTP variables are all-or-nothing: none set = email off (each
notification records "Email is not configured on this server"); some set =
startup error. Dev uses Brevo's SMTP relay; production the university's
server.
University-email login (optional): `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`
and/or `MICROSOFT_CLIENT_ID` + `MICROSOFT_CLIENT_SECRET` +
`MICROSOFT_TENANT_ID` (the university's tenant GUID) — each provider
all-or-nothing; with any provider also `SSO_ALLOWED_DOMAINS` (comma-separated)
and `API_PUBLIC_URL` (the provider redirects to
`<API_PUBLIC_URL>/api/v1/auth/sso/<provider>/callback` — register that URL
with the provider).
Web: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_EXPORT_URL`.

## 10. Scheduled Jobs

One daily job calls `POST /api/v1/internal/cron/daily` (header
`X-Cron-Secret`): fellowship ending in 60 days; APR due in 14 days (scholar)
and overdue the day after the seminar's report due date (scholar +
supervisor), while unsubmitted; meeting tomorrow, from the next meeting date
on the latest meeting logged for each scholar and supervisor. Reminders match
the exact day, so a missed run skips that day's reminders. Idempotent per day (a
`job_runs` row guards re-runs). Off (404) while `CRON_SECRET` is unset. Not a
keep-alive: it runs once a day.

## 11. Failure Scenarios

- **Database down/suspended:** API returns 5xx; no data loss (atomic
  transactions); `pool_pre_ping` drops dead connections.
- **Object storage down:** uploads/downloads fail with a visible error; all
  other flows unaffected (only metadata lives in Postgres).
- **SMTP down:** the in-app notification exists regardless; the email outcome
  is stored as `failed` with the error, and the daily job retries failed
  emails once.
- **Export service down:** export buttons show the error envelope; daily use
  is unaffected.
- **Cold start (Render free tier, ~15-min spin-down):** first request is slow;
  the web shows the sleeping owl ("Waking up the server…"). No keep-alive
  pinger. Not applicable on self-hosted production.
- **Chain edited while items are in flight:** in-flight items follow their
  `chain_snapshot`; only new submissions use the new chain.

## 12. Key Technical Decisions

| Decision | Reason |
|---|---|
| One installation per university | universities want their data on their own server; no tenant-isolation bugs possible |
| Role assignments scoped to org units | real people hold several roles; one scope function covers every level of a flexible tree |
| `ltree` for the org tree | subtree visibility is one indexed predicate, any depth |
| One generic approval engine + chain snapshot | four item types, one state machine; chain edits never corrupt in-flight items |
| Chains university-wide, not per unit | owner decision: simpler and consistent across departments |
| Files in S3-compatible storage, presigned URLs | theses are 10–50 MB; same code on R2 (dev) and Garage on a NAS (prod) |
| Optional modules as a settings table | not every university needs grants/admissions; disabled = invisible + 404 |
| JWT + rotating refresh over server sessions | stateless API; works on any host |
| Docker images for every service | one build runs on free cloud and on a NAS |
| Access token in memory, refresh in localStorage | XSS-theft risk judged low for a closed tool; upgrade path in SECURITY.md |
