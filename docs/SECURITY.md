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
  A failed login verifies a hash even for an unknown or inactive account, so
  response time gives neither away.
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
| vice_chancellor | role_assignments | university-wide, read only; acts only on a Vice Chancellor chain step |

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
| faculty / scholars directory | R own + own supervisors | R supervisees + linked faculty | R subtree‡ | CUD, assign supervisor; R subtree‡ | R | R | R |
| meetings | CRU own | CRU supervisees, sets `shared_with` | R redacted* | R redacted* | R redacted* | — | — |
| progress reports | CRU own draft/sent_back, submit | R, step | R, step (department) | R, step (department) | R, step | — | — |
| milestones (RDC register) | R own | R | R | CRUD | CRUD | R | — |
| committee members (RAC) | R own | R | R | CD | CD | — | — |
| ethics clearances | R own | R | R | CD | CD | — | — |
| seminars (schedule, hardcopy) | R own | R (own scholars') | CRUD in subtree | CRUD in subtree | R | — | — |
| seminar grades | R own after finalise | R own scholars'; finalise own scholars | R | R | R | — | — |
| to-do list | R, tick done (own) | R own scholars' | R | R | R | — | — |
| publications | CRU own, submit | R, step | R | R | R, step | — | R, step |
| conferences | CRUD own | R | R | R | R | — | R |
| documents & versions | CRU own | R, comment | — | — | — | — | — |
| thesis submissions | CR own, submit | R, step | R, step (department) | R, step (department) | R, step | R, step | R, step |
| no-dues clearance | CR own, submit | R, step | R, step (department) | R, step (department) | R, step | R | R, step |
| examiner reports | R own after release† | R after release† | R | R | R | CRU, release | R |
| thesis reviewers (invite, deadline, trace a code) | — | — | — | — | — | CRU | — |
| viva | R own | R | R | R | R | CRU | R |
| provisional certificate | R own | R | R | R | R, issue, revoke | R | R |
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
| faculty requests | — | CR for own scholars (co-supervisor, panel), answer own | CR panel in subtree, answer own | CR in subtree, answer own | — | — | — |
| comments | on any record they can R | ← | ← | ← | ← | ← | ← |
| files | on any record they can R (upload where they can U/C) | ← | ← | ← | ← | ← | ← |
| NAAC data (M9) | — | — | — | root admin only | R | — | — |
| exports | own record | supervisees | subtree | subtree | all | coursework, thesis | publications, thesis |
| audit log | — | — | — | R in subtree | R | — | — |

**Vice Chancellor** (no column above: one rule in `rbac.py`): R on every
entity the research_office column reads, and nothing else — no C, U or D
anywhere, no settings, no role assignments. Scope is university-wide. They act
on an item only at a `vice_chancellor` chain step, under the same engine rules
(§4); at that step on a thesis they may rewrite `examiners`. For meeting
minutes they count as a unit head: `unit_heads` in `shared_with` opens the
minutes to them. Office holders are listed (`GET /office-holders`) and
appointed by the root admin only.

\* **Meeting redaction:** a viewer in scope sees the full meeting only if
their role group is in `meetings.shared_with` (`unit_heads`, `research_office`,
`admins`); otherwise the API returns only `id`, `meeting_date`, scholar and
supervisor — agenda, minutes and action items are omitted server-side (and
from search results and exports). Only the main supervisor may change
`shared_with`. A co-supervisor (setting `view`/`approve`) has the supervisor
column's rights on their co-supervised scholars, except setting
`shared_with`; acting on the Supervisor step needs `approve`.

‡ **Directory visibility:** a scholar sees only their supervisor (and
co-supervisor while co-supervision is on). A supervisor sees themselves and the
people assigned with them to the same scholars. Heads and admins see their
subtree, so a Dean sees their school. Offices and the root admin see everyone.
The root admin may open a unit (`org_units.cross_unit_directory`): that unit's
heads and admins then read the faculty and scholars directories university
wide. It opens the directory only, never a scholar's records, and it is not
inherited by child units. Pickers list only faculty the caller can see; a
cross-unit co-supervisor or panel member is reached by a faculty request (below),
the root admin or an opened unit. Assignment itself is not restricted by unit.

**Faculty requests:** to reach faculty outside their view, a unit's head or
admin, or a supervisor of a scholar in the seminar, asks for a panel seat; a
department admin or the main supervisor asks for a co-supervisor. The sender
types an email and the reply is the same whether or not it belongs to faculty,
so the form cannot be used to probe the directory. Only the person asked can
accept or decline, within 7 days; accepting grants that one seminar or scholar
and never opens the directory. Thesis examiners never go through this: the Exam
Office records them and they stay confidential.

**Seminar grading:** any faculty on the seminar's panel (and, when
`seminar_graders = panel_and_attending`, any faculty who marked themselves
attending) may grade the seminar's scholars — independent of the matrix
above. Graders read the grades of that seminar. A scholar sees grades only
after their supervisor finalised; finalising is the main supervisor's (and the
co-supervisor's under `co_supervision = approve`).

† **Examiner confidentiality:** examiner names are returned only to the
Exam Office, Research Office, Vice Chancellor and root admin until the viva outcome is
recorded; reports reach the scholar and supervisor only after the Exam Office
releases them — omitted server-side, as with meeting redaction. A supervisor or co-supervisor who also heads the unit or
works in an office waits for release like any other supervisor, does not read their own scholar's
examiner names before the viva outcome is recorded, and leaves that scholar's reports to a colleague (403 `own_scholar`).
Once the viva is held the names are no secret, so everyone who can read the
reports sees them (owner decision, 2026-11-08).

**Thesis reviewers (PRD M3):** an external reviewer logs in for one assigned thesis
until their deadline or submission, and reads nothing else: `users.is_reviewer`
makes `current_principal` refuse them, so a route is closed to reviewers unless it
asks for `any_principal` or `current_reviewer` by name.
Invitation links work without a login but open only the title, abstract and the
Accept / Decline choice. The code stamped on each copy holds no personal details;
only the Exam Office may look it up, and each lookup is audited. A determined
reviewer can still screenshot or save a copy, so the code traces a leak rather
than prevents it.

**Branding:** `GET /api/v1/branding` and `/branding/logo` need no login (the
login page shows them) and return only the university's name, address and logo.
A logo is PNG or JPEG by its bytes, 500 KB at most; SVG is refused because it can
carry script. Only the root admin changes them.

**Certificate verification:** `GET /api/v1/verify/{token}` is the one route
with personal data and no login. The token is 256 random bits printed as the QR code; the
answer is name, thesis title, unit, viva date, issue date and status, never the
revocation reason or anything else. The token is redacted in `audit_log`, and
the page asks search engines not to index it.

**Grants:** the supervisor column of the grants rows means the project's PI —
any faculty member, with or without supervision rights, reads their own
projects with the ledger and UCs and may add *expenses* (never
disbursements) to them. A project member scholar sees the project and its
members, never money. A supervisor sees their scholars' fellowships but not
the fellowship ledger. Writes need the research office, or an admin over the
project's unit / the scholar's unit. An entry saved despite a warning names the
person and amount to the nearest admin over that unit, who already reads that
ledger; the warnings the person confirmed are checked server-side.

**Daily job:** `POST /internal/cron/daily` takes no JWT; it needs the
`X-Cron-Secret` header (compared in constant time) and is off (404) while
`CRON_SECRET` is unset.

**Bulk import** creates records through the same service functions as the
forms, so scope, caps and uniqueness are checked once, in one place; the
root admin may import anywhere.

Disabled modules: every route of the module → 404 `module_disabled`
regardless of role, and so does a NAAC sheet built from that module.

## 4. Approval Engine Rules (`workflow.py`)

- Only the initiator role (PRD F3) may create and submit an item; only the
  scholar edits their own `draft`/`sent_back` item; coursework clearances
  are created by the exam office.
- `can_act(user, item)`: the current step's kind resolves to
  - `supervisor` → the scholar's supervisor, or the co-supervisor when
    `settings.co_supervision = 'approve'`;
  - `department` → a `unit_head` or `admin` whose unit is the scholar's unit
    or an ancestor of it (nearest-first, but any of them may act). The
    notification goes to the nearest unit with a head/admin *other than the
    actor who moved the item*: a HoD who approved as supervisor hands the
    step to the Dean;
  - `research_office` / `exam_office` / `library` / `vice_chancellor` → any
    holder of that role.
- **No self-approval:** a user may not act on an item about themselves, and
  may not act on two consecutive steps of the same item (the engine checks
  `approval_actions`); the next eligible person must act.
- Send back: approver chooses the initiator or any earlier step; comment
  required. Illegal action/role/state → 422 `workflow_violation`.
- A progress report is **assessed**: approving it needs a rating and written
  remarks at every step (`items.py`, 422 `workflow_violation` otherwise). Its
  files are attached and removed by the scholar only while it is editable.
- Step-only fields (`plagiarism_score` — library; `examiners` — exam office,
  and the Vice Chancellor at their own step)
  are writable only by the actor of that step while it is current.
  On a thesis, scholar and Library share the files: each removes only what it
  uploaded (the Library its certificate, never the thesis).
- Send back to the initiator notifies the initiator: the scholar, or the
  exam office for a coursework clearance.
- An `approved` item is immutable for every role.

## 5. Secrets & Environment

- Never hard-code credentials; never commit secrets or `.env` files. Config
  arrives by environment, validated loudly at startup (`app/config.py`).
- Required: `DATABASE_URL`, `JWT_SECRET` (≥32 bytes), `S3_*`, `CRON_SECRET`;
  `SMTP_*` and `WHATSAPP_*` all-or-nothing (ARCHITECTURE.md §9); `SEED_PASSWORD` only for
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
- **WhatsApp:** a person's number is set and cleared only by that person
  (`PUT /auth/me/whatsapp`) and is shown only to them. Messages carry the
  event kind and a link that needs a login — never names, titles or record
  content — so nothing personal reaches Meta or a mistyped number.
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

Verified 2026-10-25 (code, tests and the approval-chain click-through):

- [x] Scope computed only in `scope.py`; 403-not-404 everywhere
- [x] Negative tests: other scholar, other unit's head/admin, office outside
      its item types, unshared meeting minutes, disabled module
- [x] No self-approval / consecutive-step approval
- [x] Admins cannot grant roles above their own unit
- [x] Rotating single-use refresh tokens; login throttling
- [x] Private bucket; presigned URLs only after `get_or_403`
- [x] No secrets in repo; loud env validation
- [x] CORS allowlist on both services
- [x] Soft delete + audit on every mutation; hashes redacted (operational
      tables excepted, DATABASE.md `audit_log`)
- [ ] HTTPS verified on every deployment — cloud dev verified (Render API and
      the Vercel web redirect to HTTPS, valid certificates); each self-hosted
      install is checked at go-live
- [x] `pip-audit` / `npm audit` clean before pilot — re-run before the pilot:
      the API image installs from version ranges, not a lockfile
