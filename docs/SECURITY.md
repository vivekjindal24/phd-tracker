# Security Guidelines

> v3 rewrite (2026-10): three fixed roles → seven roles held through scoped
> role assignments on the org tree; per-meeting minutes sharing; files in
> object storage via presigned URLs. **The API is the enforcer** — the UI
> may hide what it likes, every route re-checks.

## 1. Authentication

- **Method:** email + password; optionally single sign-on with the
  university's Google or Microsoft account (OpenID Connect, authorization
  code + PKCE, run by the API). SSO logs in an existing active user whose
  email matches the provider's **verified** email claim — no account is ever
  created by SSO. Only domains in `SSO_ALLOWED_DOMAINS` are accepted;
  Microsoft is pinned to the university's tenant. The API hands the browser a
  single-use 60-second code, never tokens in a URL.
- **Set-password / forgot-password link:** 32-byte urlsafe random,
  single-use, 72-hour expiry, sha256-hashed in the DB; using it revokes all
  the user's refresh tokens. Forgot-password answers the same whether or not
  the email exists (no account enumeration) and shares the login throttle.
- **Access token:** HS256 JWT, 30-minute expiry, held in browser memory
  (never localStorage, never a cookie). Claims carry only `sub` — roles and
  scope are loaded from the DB per request, so a revoked role takes effect
  immediately.
- **Refresh token:** 48-byte urlsafe random; DB stores only its sha256 hash.
  Single-use, rotating; `POST /auth/logout` revokes it.
- **Password hashing:** argon2id (RFC 9106 low-memory profile).
- **Accounts** are created by admins (within their unit) or by admission
  conversion — no self-registration. Deactivated users (`is_active = false`)
  cannot log in or refresh.
- **Login throttling:** 5 failed attempts per email per 15 minutes → 429.

## 2. Roles & Scope

| Role | Comes from | Scope |
|---|---|---|
| scholar | `scholars.user_id` | own records |
| supervisor | `faculty.can_supervise` | own supervisees' records |
| co-supervisor | `scholars.co_supervisor_id` (setting `co_supervision ≠ off`) | as supervisor for those scholars |
| unit_head | role_assignments (unit) | unit subtree |
| admin | role_assignments (unit) | unit subtree; root admin = whole university + settings |
| research_office | role_assignments | university-wide |
| exam_office | role_assignments | university-wide, own item types only |
| library | role_assignments | university-wide, own item types only |

A user with several roles gets the **union** of what each role allows — never
a combination that no single role allows (e.g. a supervisor who is also the
library cannot approve the supervisor step *and* the library step of the same
item: see §3).

Scope is computed in exactly one place, `services/api/app/scope.py`, and
applied to every list, detail, search, dashboard, timeline and export.
Out-of-scope access returns **403, not 404** (`get_or_403`) — a denied request
must not reveal whether the record exists.

## 3. Permission Matrix

`services/api/app/rbac.py` `MATRIX` holds this table as data. C = create,
R = read, U = update, D = soft-delete, "step" = may act on the chain step of
that kind. "—" = no access (403). All rows are additionally limited by the
role's scope (§2).

| Entity | scholar | supervisor | unit_head | admin | research_office | exam_office | library |
|---|---|---|---|---|---|---|---|
| org tree, modules, chains, settings | R (own unit) | R | R | R; root admin CUD | R | R | R |
| users & role assignments | R self | R self | R | CUD in subtree (cannot grant above own unit) | R | — | — |
| faculty / scholars directory | R own | R supervisees + faculty list | R | CUD, assign supervisor | R | R | R |
| meetings | CRU own | CRU supervisees, sets `shared_with` | R redacted* | R redacted* | R redacted* | — | — |
| progress reports | CRU own draft/sent_back, submit | R, step | R, step (department) | R, step (department) | R, step | — | — |
| milestones (RDC register) | R own | R | R | CRUD | CRUD | R | — |
| seminars (schedule, hardcopy) | R own | R (own scholars') | CRUD in subtree | CRUD in subtree | R | — | — |
| seminar grades | R own after finalise | R own scholars'; finalise own scholars | R | R | R | — | — |
| to-do list | R, tick done (own) | R own scholars' | R | R | R | — | — |
| publications | CRU own, submit | R, step | R | R | R, step | — | R, step |
| conferences | CRUD own | R | R | R | R | — | R |
| documents & versions | CRU own | R, comment | — | — | — | — | — |
| thesis submissions | CRU own, submit | R, step | R, step (department) | R, step (department) | R, step | R, step | R, step |
| examiner reports | R own after release† | R after release† | R | R | R | CRU, release | R |
| viva | R own | R | R | R | R | CRU | R |
| Shodhganga deposit | R own | R | R | R | R | R | CRU |
| bulk import | — | — | — | run in subtree | — | — | — |
| time adjustments (extensions, leave) | R own | R | R | CRD in subtree | CRD | — | — |
| leadership view | — | — | R subtree | R subtree | R all | — | — |
| courses (catalogue) | R | R | R | CRUD in subtree | R | CRUD | — |
| enrolments & grades | R own | R | R | R | R | CRUD | — |
| coursework clearances | R own | R | R, step (department) | R, step (department) | R, step | create, submit, step | — |
| admissions | — | — | R | CRUD, convert | CRUD, convert | — | — |
| fellowships | R own | R supervisees | R | CRUD | CRUD | — | — |
| projects & members | R own membership | R own (as PI) | R | CRUD | CRUD | — | — |
| ledger & UCs | — | R own projects, C expense on own projects | R | CRUD | CRUD | — | — |
| comments | on any record they can R | ← | ← | ← | ← | ← | ← |
| files | on any record they can R (upload where they can U/C) | ← | ← | ← | ← | ← | ← |
| exports | own record | supervisees | subtree | subtree | all | coursework, thesis | publications, thesis |
| audit log | — | — | — | R in subtree | R | — | — |

\* **Meeting redaction:** a viewer in scope sees the full meeting only if
their role group is in `meetings.shared_with` (`unit_heads`, `research_office`,
`admins`); otherwise the API returns only `id`, `meeting_date`, scholar and
supervisor — agenda, minutes and action items are omitted server-side (and
from search results and exports). Only the main supervisor may change
`shared_with`. A co-supervisor (setting `view`/`approve`) has the supervisor
column's rights on their co-supervised scholars, except setting
`shared_with`; acting on the Supervisor step needs `approve`.

**Seminar grading:** any faculty on the seminar's panel (and, when
`seminar_graders = panel_and_attending`, any faculty who marked themselves
attending) may grade the seminar's scholars — independent of the matrix
above. Graders read the grades of that seminar. A scholar sees grades only
after their supervisor finalised; finalising is the main supervisor's (and the
co-supervisor's under `co_supervision = approve`).

† **Examiner confidentiality:** examiner names are returned only to the
Exam Office, Research Office and root admin until the viva outcome is
recorded; reports reach the scholar and supervisor only after the Exam Office
releases them — omitted server-side, as with meeting redaction.

**Grants:** the supervisor column of the grants rows means the project's PI —
any faculty member, with or without supervision rights, reads their own
projects with the ledger and UCs and may add *expenses* (never
disbursements) to them. A project member scholar sees the project and its
members, never money. A supervisor sees their scholars' fellowships but not
the fellowship ledger. Writes need the research office, or an admin over the
project's unit / the scholar's unit.

**Daily job:** `POST /internal/cron/daily` takes no JWT; it needs the
`X-Cron-Secret` header (compared in constant time) and is off (404) while
`CRON_SECRET` is unset.

**Bulk import** creates records through the same service functions as the
forms, so scope, caps and uniqueness are checked once, in one place; the
root admin may import anywhere.

Disabled modules: every route of the module → 404 `module_disabled`
regardless of role.

## 4. Approval Engine Rules (`workflow.py`)

- Only the initiator role (PRD F3) may create and submit an item; only the
  scholar edits their own `draft`/`sent_back` item; coursework clearances
  are created by the exam office.
- `can_act(user, item)`: the current step's kind resolves to
  - `supervisor` → the scholar's supervisor, or the co-supervisor when
    `settings.co_supervision = 'approve'`;
  - `department` → a `unit_head` or `admin` whose unit is the scholar's unit
    or an ancestor of it (nearest-first, but any of them may act);
  - `research_office` / `exam_office` / `library` → any holder of that role.
- **No self-approval:** a user may not act on an item about themselves, and
  may not act on two consecutive steps of the same item (the engine checks
  `approval_actions`); the next eligible person must act.
- Send back: approver chooses the initiator or any earlier step; comment
  required. Illegal action/role/state → 422 `workflow_violation`.
- Step-only fields (`plagiarism_score` — library; `examiners` — exam office)
  are writable only by the actor of that step while it is current.
- An `approved` item is immutable for every role.

## 5. Secrets & Environment

- Never hard-code credentials; never commit secrets or `.env` files. Config
  arrives by environment, validated loudly at startup (`app/config.py`).
- Required: `DATABASE_URL`, `JWT_SECRET` (≥32 bytes), `S3_*`, `CRON_SECRET`;
  `SMTP_*` all-or-nothing (ARCHITECTURE.md §9); `SEED_PASSWORD` only for
  seeding.
- Dev secrets live in each platform's settings (Neon, Render, Vercel,
  Cloudflare); production secrets in the server's compose `.env` file,
  readable only by root, never in git. Rotate any exposed secret immediately.

## 6. API Security

- All routes under `/api/v1`; export-service endpoints under `/internal` with
  the same JWT auth and the same scope; the export service never holds a
  credential of its own. `/internal/cron/daily` additionally requires
  `X-Cron-Secret` and no user token.
- **Validation:** Pydantic on every boundary (Literals mirror DB CHECKs);
  cross-row rules (duplicates, UGC cap, chain step) enforced by DB
  constraints + the engine.
- **Files:** presigned URLs are issued only after the owner record's
  `get_or_403`; upload URLs bind content type and max size and expire in
  5 minutes; download responses force `Content-Disposition: attachment` with a
  sanitised filename. The bucket is private — no public objects.
- **CORS:** explicit origin allowlist (`CORS_ORIGINS`) on API and export —
  never `*`.
- **Errors:** one envelope `{"error": {code, message, details}}`; messages
  never leak internals; unhandled exceptions log server-side, return 500.
- **Audit:** every mutation writes `audit_log`; password and token hashes are
  redacted from snapshots.

## 7. Token Storage Tradeoff (known, accepted)

The refresh token sits in localStorage: an XSS bug could steal it. Judged
low-risk for a closed tool with no third-party scripts. **Upgrade path:**
httpOnly SameSite=Strict cookie behind a Next route-handler proxy.

## 8. Data Protection

- **Sensitive data:** personal details, meeting minutes, research
  summaries, theses before publication, grades, fellowship amounts.
- Transport: HTTPS everywhere (platform TLS in dev; Caddy automatic HTTPS in
  production). At rest: provider encryption in dev; full-disk encryption on
  the production NAS is a deployment requirement.
- **Retention:** records are permanent — they ARE the PhD trail. Soft-delete
  only; deletion requests escalate to the root admin.
- **Backups (production):** nightly `pg_dump` + bucket copy to a second
  disk by the cron container (`deploy/cron/run.sh`); restore
  (`deploy/README.md`) tested before go-live.

## 9. Logging

- Never log passwords, tokens, token hashes, file contents or meeting
  minutes.
- Log: auth events (success/failure), role-assignment changes, workflow
  actions, email failures, errors with context.

## 10. Security Checklist

- [ ] Scope computed only in `scope.py`; 403-not-404 everywhere
- [ ] Negative tests: other scholar, other unit's head/admin, office outside
      its item types, unshared meeting minutes, disabled module
- [ ] No self-approval / consecutive-step approval
- [ ] Admins cannot grant roles above their own unit
- [ ] Rotating single-use refresh tokens; login throttling
- [ ] Private bucket; presigned URLs only after `get_or_403`
- [ ] No secrets in repo; loud env validation
- [ ] CORS allowlist on both services
- [ ] Soft delete + audit on every mutation; hashes redacted
- [ ] HTTPS verified on every deployment
- [ ] `pip-audit` / `npm audit` clean before pilot
