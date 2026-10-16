# Testing

> v2 rewrite: bench test-site instructions are superseded. Each service owns
> its suite; CI runs all of them on every push/PR.

## 1. What to Verify

- Workflow transitions: every legal transition per role, plus illegal ones
  (e.g. supervisor tries `submit` → 422 `workflow_violation`).
- Permission boundaries: scholar cannot read another scholar's records (the
  v1-gap regression), 403-not-404 on out-of-scope ids, export restricted to
  admin.
- Data rules: duplicate APR → 409, UGC designation cap → 409, soft delete
  keeps rows invisible, audit rows written on every mutation.
- Export correctness: valid `%PDF` magic bytes, CSV escaping, empty-state
  pages, error propagation (never a silently blank PDF).

## 2. Services & Suites

### services/api — pytest
- Runs against **real Postgres DDL**: `conftest.py` applies
  `alembic upgrade head` to the scratch DB, truncates between tests.
- Fixtures mint the three roles directly (`admin@x.edu`, supervisor
  `meera@x.edu`, scholars `a@x.edu`/`b@x.edu`).
- Files: `tests/test_auth.py`, `test_rbac.py` (incl. the v1-gap regression),
  `test_workflow.py`, `test_search.py`.
- Lint: `ruff check .` must be clean.

```bash
# local (venv ~/.venvs/phd-tracker-api, scratch DB phd_tracker_test)
DATABASE_URL="postgresql+psycopg://$(whoami)@localhost:5432/phd_tracker_test" \
  JWT_SECRET=test-secret-0123456789abcdef0123456789 \
  pytest
ruff check .
```

CI: `ci.yml` job `api` uses a `postgres:16` service container (pg_trgm needs
real Postgres), runs the migration chain, then the suite.

### services/export — node:test
- Spins a stub `node:http` API server; verifies auth header forwarding,
  PDF/CSV bytes, empty states, error passthrough.
```bash
npm ci && npm run typecheck && npm test
```

### web — build + click-through
- `npm run build` is the type gate (Next 16 + strict TS).
- Manual/Playwright click-through of the three seeded roles (Phase 3
  checklist): admin full access + APR PDF download; scholar sees only own
  rows, edits + submits own draft, cannot edit a submitted one; supervisor
  sees only own scholars, comments + approves, approved report immutable;
  direct-URL pages the API denies render the API's 403, not the data.

## 3. Local Stack

```bash
docker compose up            # Postgres + API + export
# web: cd web && npm run dev (see web/README.md for NEXT_PUBLIC_* vars)
```

The compose stack doubles as the smoke test: `/api/v1/healthz` on :8900 and
`/healthz` on :8902, login with the seeded admin, and the flows in UX_FLOWS.md.

## 4. Coverage

- No percentage theater: the priority order is workflow transitions
  (compliance correctness) > permission denials (negative tests) > data
  rules > export bytes > UI build. The API suite covers the first four;
  the click-through covers the fifth.
- Any new non-trivial API route adds its negative test in the same change
  (AGENTS.md §9 — the security matrix must still hold, including negatives).

## 5. Definition of Done

- [ ] `ruff check .` + `pytest` green (api)
- [ ] `npm run typecheck` + `npm test` green (export)
- [ ] `npm run build` green (web)
- [ ] `alembic upgrade head` verified against a scratch DB when DDL changed
- [ ] Three-role click-through passes on the local stack
- [ ] No unrelated files changed; docs updated where behavior changed