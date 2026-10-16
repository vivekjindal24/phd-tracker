# Security Guidelines

> v2 rewrite: Frappe sessions → JWT + rotating refresh tokens. The permission
> matrix is unchanged in substance; enforcement moved from DocType JSON into
> `services/api/app/rbac.py`.

## 1. Authentication

- **Method:** email + password only (university-internal tool; no OAuth until
  a pilot asks).
- **Access token:** HS256 JWT, 30-minute expiry, held in browser memory
  (module variable — never localStorage, never a cookie).
- **Refresh token:** 48-byte urlsafe random; the DB row stores only its
  sha256 hash. Single-use and rotating: every refresh revokes the presented
  token and issues a new pair. Kept in localStorage; `POST /auth/logout`
  revokes it.
- **Password hashing:** argon2id (RFC 9106 low-memory profile, tuned for the
  free-tier instance CPU — see `app/auth/service.py`).
- **User registration** (`POST /auth/register`) is admin-only — explicit
  check in the route, not a matrix cell.

## 2. Authorization

Roles: **scholar**, **supervisor**, **admin** (v2 drops the "PhD"/"Research
Office" prefixes; substance unchanged). The matrix lives as data in
`services/api/app/rbac.py` (`MATRIX`); the UI may hide what it likes, but
**the API is the enforcer** — every route re-checks.

| Entity | scholar | supervisor | admin |
|---|---|---|---|
| scholars | read (own) | read (own supervisees) | full |
| supervisors | read (directory) | read | full |
| meetings | create, read, write (own) | create, read, write (own scholars') | full |
| progress reports | create, read, write, submit, resubmit (own) | read, write (comment), approve, send_back | full + all actions |
| milestones | read (own) | create, read, write (own scholars') | full |

Row-level scope (`rbac.scope()`):
- A scholar sees **only their own** records; a supervisor only their
  supervisees' (subquery on `scholars.supervisor_id`). The supervisors
  directory is readable by all roles (a public faculty list).
- Cross-record access returns **403, not 404** (`get_or_403`) — a denied
  request must not leak whether the record exists.
- The v1 gap ("scholar can read another scholar's records") is closed by
  construction and covered by a regression test
  (`test_scholar_cannot_read_another_scholars_records`).

## 3. Workflow Role-gating

`workflow.py TRANSITIONS` additionally gates by role per state: only
scholar/admin submit or resubmit; only supervisor/admin approve or send back.
An illegal combination → 422 `workflow_violation`. An **approved report is
immutable for every role** — it is the compliance record.

## 4. Secrets & Environment

- Never hard-code credentials; never commit production secrets; never commit
  `.env` files. All config arrives by environment and is validated loudly at
  startup (`app/config.py`).
- Required: `DATABASE_URL`, `JWT_SECRET` (≥32 bytes, startup fails if
  shorter); `SEED_PASSWORD` only for seeding.
- Deploy-time secrets (Neon, Render, Vercel) live in each platform's
  environment settings — never in this repo. Rotate any exposed secret
  immediately.

## 5. API Security

- All routes versioned under `/api/v1`; endpoints the export service consumes
  live under `/internal` with the same JWT auth (admin-only), the caller's
  token forwarded verbatim — the export service never holds a service
  credential of its own.
- **Validation:** Pydantic validates every boundary (Literals mirror the DB
  CHECK constraints); cross-row rules (duplicate APR, UGC cap) are enforced
  by partial unique index + router checks.
- **CORS:** explicit origin allowlist from `CORS_ORIGINS` (API) /
  `CORS_ORIGINS` (export) — never `"*"` with credentials.
- **Errors:** one envelope (`{"error": {code, message, details}}`); messages
  never leak internals. Unhandled exceptions log server-side and return a
  generic 500.
- **Audit:** every mutation writes an `audit_log` row (actor, action,
  prev/new snapshots). Soft-delete only; no hard deletes.

## 6. Token Storage Tradeoff (known, accepted)

The refresh token sits in localStorage: an XSS bug could steal it. Judged
low-risk for a closed, no-third-party-script tool. **Upgrade path:** move
the refresh token to an httpOnly SameSite=Strict cookie behind a Next route
handler proxy (noted in `web/src/lib/api.ts`); nothing else changes.

## 7. Data Protection

- **Sensitive data:** emails, meeting minutes, research summaries, GitHub
  URLs. Transport is HTTPS (Vercel/Render endpoints are TLS by
  default); at-rest is Neon's storage encryption.
- **Retention:** records are permanent — they ARE the PhD's audit trail.
  Soft-delete only. Deletion requests escalate to the owner; never
  auto-delete compliance records.
- **Export:** PDF/CSV generation is restricted to admin (the research
  office); a scholar/supervisor token → 403.

## 8. Logging

- Never log passwords, token hashes, or full record contents.
- Log: auth events, workflow transitions, errors with context (the API logs
  tracebacks for 500s; the export service logs render failures).

## 9. Security Checklist

- [x] Permission matrix enforced server-side (API); 403-not-404 row scope
- [x] Workflow actions role-gated; approved reports immutable
- [x] Rotating single-use refresh tokens; hashed at rest
- [x] No secrets in repo; loud env validation at startup
- [x] CORS allowlist on both services, never `*`
- [x] Soft-delete-only retention + audit_log on every mutation
- [x] Scholar-visibility regression test in CI
- [ ] HTTPS verified on deployed URLs (Phase 4 checklist)
- [ ] `pip-audit` / `npm audit` before pilot