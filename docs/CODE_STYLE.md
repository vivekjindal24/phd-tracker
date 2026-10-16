# Code Style & Conventions

> v2 rewrite: Frappe house style is superseded. Three codebases, three
> toolchains, one set of principles. The v1 rules that survive are carried
> over verbatim below.

## 1. General Principles (all services)

- Prefer readable code over clever code; keep functions focused (<50 lines),
  files small (200–400 typical, 800 max).
- Reuse what's already here before writing new: the shared crud helpers,
  `get_or_403`, the error envelope, the UI kit (`web/src/lib/ui.tsx`).
- Platform first: DB constraint over app code, `<input type="date">` over a
  picker library, CSS over JS.
- **Fail loudly** — no swallowed exceptions, no silent fallbacks. This is
  compliance software; silent failure is the worst outcome.
- No secrets in code; config by environment, validated at startup.
- `ponytail:` comments mark deliberate simplifications with a known ceiling
  and their upgrade path (e.g. the count-then-insert UGC cap check in
  `scholars.py`).
- exFAT junk: `._*` AppleDouble and `__pycache__` are gitignored — never
  stage or edit them; delete before running directory-scanning tools.

## 2. services/api (Python/FastAPI)

- **Tools:** ruff (lint, configured in `pyproject.toml`), pytest.
- Async routes with async SQLAlchemy sessions — never sync sessions from
  async routes. No blocking I/O in handlers.
- Pydantic validates every boundary; Literals mirror the DB CHECK
  constraints exactly.
- Routers stay thin; business rules live in `rbac.py`/`workflow.py` and the
  crud helpers — not in UI, not in scripts, not duplicated per route.
- Errors: raise `ApiError` (`app/errors.py`) — it maps to the uniform
  envelope. Never `print()`; never return error strings.
- One state machine: APR state comes only from `workflow.TRANSITIONS`.
- Naming: snake_case functions, UPPER_SNAKE_CASE constants, PascalCase
  classes. Type hints on every signature.
- Migrations go through Alembic in the same change as the model; DATABASE.md
  updates in the same commit.

## 3. services/export (Node/TypeScript)

- **Tools:** `tsc --noEmit` strict, node:test.
- The service stays stateless: no tables, no auth logic — it forwards the
  caller's token and renders what the API returns. Never add a service
  credential or a DB connection here.
- zod validates every API response before rendering (a malformed upstream is
  a 500 `export_failed`, never a silently blank PDF).
- Imports use `.ts` extensions (allowed via tsconfig `allowImportingTsExtensions`
  + noEmit; runtime is `tsx`).

## 4. web (Next.js App Router)

- Client components (`"use client"`) behind the auth gate; the API is the
  security enforcer — the UI only hides what the API already denies.
- Design tokens and components live in `globals.css`, `(app)/app.css`, and
  `src/lib/ui.tsx` — no Tailwind, no UI library, no new font stacks
  (DESIGN_SYSTEM.md governs the look).
- State conveyed text-first, color second; semantic HTML (`<dl>` for
  key-value, real `<table>` for registers, `<form>` with labels).
- Naming: components PascalCase, hooks `use*`, CSS classes kebab-case.
- Env vars: only `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_EXPORT_URL` (they
  are public by design — the JWT is the secret, and it never ships in the
  bundle).
- Turbopack persistent cache is off (`next.config.ts`) — the exFAT working
  volume breaks its cache DB; Vercel builds are unaffected.

## 5. Git

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `chore:`, `perf:`, `ci:` — subject line, body only when it adds context.
- Never commit: `.env` files, secrets, `._*`, `__pycache__`, `.next/`,
  `node_modules/`.
- Keep changes to the touched sections — don't rewrite whole documents or
  reformat untouched files.

## 6. Do / Don't

**Do**
- Extend existing patterns: a new workflow action goes in `TRANSITIONS`; a
  new permission in `MATRIX`; a new page composes the UI kit.
- Write the negative test with the route (a scholar must not read another
  scholar's record — forever).
- Update the affected doc section in the same commit as the change that
  makes it true.

**Don't**
- Don't put business logic in the web app, the export service, or one-off
  scripts.
- Don't hand-edit data in the database — Alembic migrations only.
- Don't add a dependency for what a few lines of stdlib/platform code do.
- Don't catch an exception just to log-and-continue — surface it (uniform
  envelope, user-visible message, or a loud log with context).
- Don't touch `phd_tracker/` (the frozen v1 Frappe app).