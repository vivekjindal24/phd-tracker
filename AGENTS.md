# AI Coding Agent Instructions

## 1. Project Context

- **Project:** PhD Tracker v2 — cloud-native rewrite.
- **Purpose:** Supervisor–scholar workspace for Indian university PhD programs.
  The daily-use layer (meetings, progress reports, milestones) is the product;
  UGC compliance paperwork is generated as a byproduct.
- **Stack:** polyglot monorepo, no single framework:
  - `services/api` — Python/FastAPI: auth (JWT + rotating refresh tokens), all
    entities, the APR workflow state machine, search, audit. Sole owner of the
    Postgres schema `core`.
  - `services/export` — Node/TypeScript: stateless PDF/CSV exports; holds zero
    auth/data logic, reads only via the API's internal endpoints with the
    caller's token forwarded.
  - `web` — Next.js (App Router) on Vercel.
  - `phd_tracker/` — Frappe v1 app, **frozen reference only, never modify**.
- **Deployment:** everything on cloud platforms at $0 free tiers — Neon Postgres,
  Koyeb (API), Render (export), Vercel (web); GitHub Actions → GHCR images.
  Services are stateless and idle-spin-down tolerant; expect cold starts.
- **Primary Users:** PhD scholars, PhD supervisors, research office admins.
  The buyer (registrar/dean) gets PDF exports, never a login.

## 2. Source of Truth

Before any non-trivial change, read the relevant document in `docs/`:
PRD.md, DESIGN_SYSTEM.md, ARCHITECTURE.md, DATABASE.md, SECURITY.md,
CODE_STYLE.md, TESTING.md, UX_FLOWS.md.

Do not contradict these documents. If a requirement and reality conflict, identify
the conflict and ask — do not guess.

## 3. General Rules

- Enforce nothing in the UI that isn't enforced server-side (SECURITY.md).
- Do not invent business requirements; PRD.md non-goals are real non-goals.
- Never touch secrets; never commit `.env` files. Config arrives by environment
  only and is validated loudly at startup (app/config.py).
- Soft-delete only, never hard delete. Every mutation writes an `audit_log` row.
- This repository lives on an exFAT volume: `._*` AppleDouble files and
  `__pycache__` are junk — gitignored; never stage or edit them. They break
  tools that scan directories (alembic chokes on `._*.py`): delete them
  (`find . -name '._*' -delete`) before running such tools. Python virtual
  environments must live off this volume (e.g. `~/.venvs/phd-tracker-api`) —
  exFAT breaks wheel RECORD verification.

Standing engineering principles (owner directive, applies to every change):
- **Clean structure, strict separation:** each service is self-contained; the
  export service owns no tables and no auth; business logic lives in the API's
  service/rbac/workflow modules, never in UI or scripts.
- **No dead or duplicate code:** when touching an area, delete what it no longer
  needs.
- **Consistent naming** per CODE_STYLE.md — no new conventions.
- **Error handling everywhere:** no swallowed exceptions, no silent fallbacks —
  uniform error envelope (`app/errors.py`), every failure surfaces to the user
  or the log.
- **One source of state:** APR lifecycle state lives in the `workflow.py` state
  machine — never in ad-hoc status fields or client-side variables.
- **API surface stays structured:** all routes versioned under `/api/v1`;
  endpoints the export service consumes live under `/internal` with the same
  JWT auth, not scattered.
- **Data stays documented:** any schema change updates DATABASE.md in the same
  commit.

## 4. Planning

Before implementing a non-trivial task:
1. Read the relevant doc(s) above.
2. Read the touched model/router (`app/models.py`, `app/routers/`).
3. List affected files (models, migration, routers, docs, tests).
4. Is it a schema change? Then it needs an Alembic migration in the same change.
5. State a concise plan before writing.

## 5. Implementation

- API: async routes with async SQLAlchemy sessions (never sync sessions from
  async routes); ruff-clean; Pydantic validates every boundary.
- Export: TypeScript strict; `npm run typecheck` clean.
- Data migrations go through Alembic (`alembic/versions/`) — never raw SQL
  against a live DB by hand.
- No cross-schema writes; the export service reads via internal REST only.

## 6. Validation

After implementation (run what applies; report what was skipped):
1. API: `ruff check .` + `pytest` (needs `DATABASE_URL` and a live Postgres;
   venv: `~/.venvs/phd-tracker-api`).
2. Export: `npm run typecheck` + `npm test`.
3. Migration sanity: `alembic upgrade head` against a scratch DB when DDL changed.
4. Confirm no unrelated files changed (`git status`).
5. Report honestly: what was run, what was skipped, what's unresolved.

## 7. Documentation

Update docs/ when a change alters: product behavior (PRD), schema (DATABASE),
permissions (SECURITY), flows (UX_FLOWS), or conventions (CODE_STYLE). Keep the
change to the affected section — don't rewrite whole documents.

## 8. Conflict Handling

If docs conflict with each other or with the code: identify the conflict
explicitly and ask for a decision. Specific rules win over general intent.
Never resolve a conflict by silently implementing a third option.

## 9. Completion Criteria

A task is complete only when:
- The PRD acceptance criteria for the touched feature hold.
- Lint/tests pass for the touched services.
- No unintended files changed.
- Security matrix (SECURITY.md §2) still holds — including negative cases
  (e.g. a scholar cannot read another scholar's records).
- Docs updated where behavior changed.