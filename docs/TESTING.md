# Testing

> v3 rewrite (2026-10): scope and approval-engine coverage across seven
> roles and a multi-level org tree. Each service owns its suite; CI runs all
> of them on every push/PR.

## 1. What to Verify (priority order)

1. **Approval engine:** every default chain end to end; send back to the
   initiator and to each earlier step; resubmit restarts from step 1;
   chain snapshot (editing a chain doesn't affect in-flight items);
   wrong actor → 422; no self-approval; no consecutive-step approval by the
   same person; approved items immutable; step-only fields writable only by
   their step.
2. **Scope negatives (403, never 404):** scholar → another scholar;
   supervisor → non-supervisee; HoD of unit A → unit B record; Dean → a
   school they don't head; exam office → publications; library →
   coursework; admin granting a role above their unit; co-supervisor
   loses access when the setting is `off` and acts on the Supervisor step
   only under `approve`; unshared meeting
   minutes redacted in detail, list, search and export; multi-role user gets
   the union, never more.
3. **Data rules:** duplicates → 409 (`duplicate_apr`, `uq_thesis_active`,
   …); UGC cap → 409; one root unit; role-scope shape; soft delete hides
   rows; audit row on every mutation with hashes redacted.
4. **Modules:** disabled module → 404 on every route and absent from search.
5. **Files:** presign denied for out-of-scope records; size cap; only
   `ready` files downloadable.
6. **Notifications:** created in the same transaction as the event; SMTP
   failure recorded, never raised to the user; muted categories skip email.
7. **Exports:** `%PDF` magic bytes, CSV escaping, empty-state pages,
   redaction, error propagation.
8. **UI build** and the click-through below.

## 2. Services & Suites

### services/api — pytest
- Runs against **real Postgres DDL**: `conftest.py` applies
  `alembic upgrade head` to a scratch DB and truncates between tests.
- Fixtures build a small tree (Root → School A {Dept A1, Dept A2}, School B
  {Dept B1}) and mint one user per role, plus a multi-role user (supervisor +
  HoD of A1 + admin of A1).
- Object storage: tests run against a MinIO container (CI service) — no
  mocks for the S3 API. SMTP: an in-process `aiosmtpd` sink.
- Files: `tests/test_auth.py`, `test_scope.py`, `test_rbac.py`,
  `test_workflow.py` (parametrised over all four item types),
  `test_meetings_sharing.py`, `test_modules.py`, `test_files.py`,
  `test_notifications.py`, `test_search.py`, one file per module.
- Lint: `ruff check .` clean.

```bash
# venv off the exFAT volume: ~/.venvs/anveshan-api; scratch DB anveshan_test
DATABASE_URL="postgresql+psycopg://$(whoami)@localhost:5432/anveshan_test" \
  JWT_SECRET=test-secret-0123456789abcdef0123456789 \
  S3_ENDPOINT=http://localhost:9000 S3_BUCKET=anveshan-test \
  pytest
ruff check .
```

CI `api` job: `postgres:16` + `minio` service containers, migration chain,
suite.

### services/export — node:test
Stub `node:http` API server; auth header forwarding, PDF/CSV bytes, empty
states, redacted meetings, error passthrough.
```bash
npm ci && npm run typecheck && npm test
```

### web — build + click-through
- `npm run build` is the type gate.
- Playwright click-through with the seeded users (§3), one spec per UX flow:
  scholar submits APR → supervisor → HoD/department admin → research office;
  library sends a publication back to the supervisor step; HoD sees
  redacted minutes until shared; Dean sees only their school; root admin
  edits a chain and toggles a module (nav item disappears); direct URLs the
  API denies render the 403 state.
- Visual: screenshots at 375 / 768 / 1440 in light and dark; reduced-motion
  run (no confetti); axe accessibility scan with zero serious violations.

## 3. Local Stack

```bash
docker compose up            # Postgres + MinIO + API + export
# web: cd web && npm run dev
```

Smoke test: `/api/v1/healthz` (:8900), `/healthz` (:8902), log in as each
seeded role, run the flows in UX_FLOWS.md.

## 4. Coverage

No percentage theatre: the priority order in §1 is the order of investment.
Any new route ships with its negative test (scope + matrix) in the same
change; any new item type joins the parametrised workflow suite.

## 5. Definition of Done

- [ ] `ruff check .` + `pytest` green (api)
- [ ] `npm run typecheck` + `npm test` green (export)
- [ ] `npm run build` green (web); Playwright flows pass
- [ ] `alembic upgrade head` verified against a scratch DB when DDL changed
- [ ] Light + dark screenshots reviewed; axe clean; reduced-motion checked
- [ ] No unrelated files changed; docs updated where behaviour changed
