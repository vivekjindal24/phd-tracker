# AI Coding Agent Instructions

## 1. Project Context

- **Project:** Anveshan (repo: `phd-tracker`) — v3 rebuild from scratch.
- **Purpose:** the one-stop research system of an Indian university.
  Scholars, supervisors, unit heads (HoD, Dean), scoped admins and the
  central offices (research office, exam office, library) work in one place;
  UGC compliance records fall out of daily use.
- **Stack:** polyglot monorepo, no single framework:
  - `services/api` — Python/FastAPI: auth (JWT + rotating refresh tokens),
    org tree, scoped role assignments (`scope.py`), the permission matrix
    (`rbac.py`), the generic approval engine (`workflow.py`), optional
    modules, notifications, files (presigned S3), search, audit. Sole owner
    of the Postgres schema `core`.
  - `services/export` — Node/TypeScript: stateless PDF/CSV exports; zero
    auth/data logic; reads only via the API's `/internal` endpoints with the
    caller's token forwarded.
  - `web` — Next.js (App Router), warm academic claymorphism with the owl.
- **Deployment:** one installation per university. Dev/test on free cloud
  tiers (Neon, Render, Vercel, Cloudflare R2); production self-hosted on a
  server/NAS via Docker Compose (Postgres, Garage, API, export, web, Caddy, cron); see `deploy/README.md`.
  Same images everywhere; only environment differs.
- **Primary Users:** scholar, supervisor, unit_head, admin (scoped),
  research_office, exam_office, library — one login may hold several roles.

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
  environments must live off this volume (e.g. `~/.venvs/anveshan-api`) —
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
- **One source of state:** the state of every approvable item lives in the
  approval columns and changes only through the `workflow.py` engine — never
  in ad-hoc status fields or client-side variables. Visibility is computed
  only in `scope.py`.
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
   venv: `~/.venvs/anveshan-api`).
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
- Security matrix (SECURITY.md §3) still holds — including negative cases
  (a scholar cannot read another scholar's records; a unit head cannot read
  outside their subtree; unshared meeting minutes stay redacted).
- Docs updated where behavior changed.