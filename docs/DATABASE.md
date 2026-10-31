# Database

> v3 rewrite (2026-10): org tree, scoped role assignments, generic approval
> engine, optional-module tables and object-storage file metadata. The
> authoritative DDL is the Alembic chain in `services/api/alembic/versions/`;
> this document describes it and must change in the same commit as any
> migration.

## 1. Engine & Access

- **Postgres 16** — Neon in dev/test, a `postgres:16` container in
  self-hosted production, a `postgres:16` service container in CI.
  Extensions: `ltree` (org tree), `pg_trgm` (search), `citext` (emails).
- Only `services/api` connects. The export service reads via the API's
  `/internal` endpoints; the web holds no DB access.
- `DATABASE_URL` (`postgresql+psycopg://…`) validated at startup. Small pool
  (`pool_size=2, max_overflow=3`) for Neon's free tier; `pool_pre_ping` on.
- **File bytes are never stored in Postgres** — only metadata (`files`); bytes
  live in S3-compatible storage.

## 2. Naming Conventions

- Tables: plural snake_case in schema `core`.
- Columns: snake_case; ids are `uuid` (`gen_random_uuid()`).
- Every domain row carries `created_at` / `updated_at` (`timestamptz`) and
  `deleted_at` (soft-delete marker). Soft delete only — no hard deletes.
- Enums are `text` + `CHECK` constraints (no Postgres enum types); values
  mirror the Pydantic Literals exactly, and vice versa.
- Approvable tables share the **approval columns** (§3.4).

## 3. Tables

### 3.1 Organisation & people

**org_units** — the university tree. `parent_id` FK self (NULL only for the
root; partial unique index `uq_org_root` guarantees exactly one root),
`name`, `kind` (free-text label: "University", "School", "Department", …),
`code` (UNIQUE), `path` `ltree` (UNIQUE, GiST-indexed; maintained by the API
on insert/move). A unit can be soft-deleted only when it has no live child
units, scholars or faculty.

**users** — login identity: `email` (citext, UNIQUE), `password_hash`
(NULL until the person sets one — invited or SSO-only accounts cannot log in
by password), `full_name`, `is_active`, `email_muted` text[] (notification categories the
user muted for email; CHECK ⊆ categories in §3.7), `whatsapp_number` (NULL =
no WhatsApp; set only by the person themself, which is the opt-in; CHECK E.164
`^\+[1-9][0-9]{7,14}$`), `whatsapp_muted` text[] (as `email_muted`, for
WhatsApp).

**role_assignments** — `user_id` FK, `role` CHECK (`unit_head` / `admin` /
`research_office` / `exam_office` / `library`), `unit_id` FK org_units.
CHECK `ck_role_scope`: `unit_head` and `admin` require `unit_id`; the three
office roles require `unit_id IS NULL` (university-wide). Partial unique
`(user_id, role, unit_id) WHERE deleted_at IS NULL`. An `admin` at the root
unit is the **root admin**. Scholar and supervisor are not rows here — they
come from the profile tables below.

**faculty** — `user_id` FK (UNIQUE), `unit_id` FK, `employee_id`,
`designation` CHECK (Professor / Associate Professor / Assistant Professor),
`max_scholars` (default from designation: 8 / 6 / 4), `can_supervise` bool
(default true). A faculty member with `can_supervise` holds the supervisor
role.

**scholars** — `user_id` FK (UNIQUE), `unit_id` FK, `roll_number` (UNIQUE),
`research_title`, `admission_date`, `stage` CHECK (Registered / Coursework /
Proposal Approved / Pre-Synopsis / Thesis Submitted / Viva / Degree Awarded,
default Registered), `supervisor_id` FK faculty (indexed, nullable),
`co_supervisor_id` FK faculty (indexed, nullable; CHECK ≠ `supervisor_id`;
honoured only while `settings.co_supervision ≠ 'off'`), `left_on` date +
`left_reason` CHECK (withdrawn / cancelled) — both set or both NULL
(`ck_scholars_left`). The admission a scholar came from is
`admissions.scholar_id`. Only **current** scholars (not left, not Degree
Awarded — `directory.is_current()`) count toward a supervisor's UGC cap;
over-cap assignment, or bringing a scholar back over the cap →
409 `supervisor_cap_exceeded` (`directory.py`, see SECURITY.md).

**time_adjustments** — `scholar_id` (indexed), `kind` CHECK (extension /
relaxation / maternity_leave / medical_leave / other_leave), `start_date`,
`end_date` (CHECK ≥ start), `resolution_number`, `notes`. Extensions and the
relaxation move the scholar's maximum-duration date; leave is checked
against its own limit (`app/duration.py`).

### 3.2 Settings

**modules** — `key` PK CHECK (`publications`, `conferences`, `documents`,
`coursework`, `admissions`, `fellowships`, `projects`, `ledger`), `enabled`
bool, `updated_by`, `updated_at`. Seeded with every key; core features have
no row (always on).

**settings** — single row (`id` = 1, CHECK): `co_supervision` CHECK
(`off` / `view` / `approve`, default `off`), `require_hardcopy` bool (default
false), `require_no_dues` bool (default false: a thesis waits for an approved
no-dues clearance while true), `seminar_graders` CHECK (`panel` / `panel_and_attending`, default
`panel`), `seminar_rubric` jsonb (ordered `[{"name", "max"}]`, non-empty),
`min_coursework_credits` numeric(3,1) (default 12, CHECK 0–40) and
`min_coursework_cgpa` numeric(4,2) (default 5.5, CHECK 0–10),
`max_duration_years` (default 6, CHECK 3–12), `max_extension_days` (730),
`max_relaxation_days` (730), `max_maternity_leave_days` (240) — the UGC rule
values the university's ordinance sets, `updated_by`, `updated_at`.
University-wide switches that are not modules live here.

**approval_chains** — `item_type` PK CHECK (`progress_report`,
`publication`, `coursework_clearance`, `thesis_submission`,
`no_dues_clearance`), `steps` jsonb:
ordered array of `{"kind": …}` where kind ∈ `supervisor` / `department` /
`research_office` / `exam_office` / `library`; CHECK non-empty array (kinds
validated by Pydantic). One chain per item type, university-wide. Seeded with
the PRD F3 defaults. `updated_by`, `updated_at`.

### 3.3 Daily use

**meetings** — `scholar_id`, `supervisor_id` (FKs, indexed), `meeting_date`,
`agenda`, `minutes`, `action_items`, `next_meeting_date`, `shared_with`
text[] CHECK ⊆ {`unit_heads`, `research_office`, `admins`} (default `{}` =
private to scholar + supervisor), `created_by`. Redaction for unshared
viewers happens in the API (`scope.py`), never in the client.

**milestones** (the RDC / committee register) — `scholar_id` (indexed),
`milestone_type` CHECK (coursework / proposal_approval / rac_review /
pre_synopsis / thesis_submission / viva / degree_awarded), `status` CHECK
(Pending / Approved / Rejected, default Pending), `approval_body` CHECK
(RDC / DPGC / DRC / RAC / Other), `resolution_number`, `resolution_date`,
`notes`.

### 3.3b Progress seminars (PRD F15)

**seminars** — `unit_id` FK (scope anchor), `title`, `starts_at`
timestamptz, `venue`, `report_due` date, `report_year`, `period`, `notes`,
`status` CHECK (scheduled / cancelled), `created_by`. Cancelling sets status;
rows are never deleted.
**seminar_scholars** — `seminar_id`, `scholar_id` (UNIQUE pair),
`hardcopy_received_on` date, `draft_points` jsonb (supervisor's working list
before finalising), `finalised_at`, `finalised_by`.
**seminar_panel** — `seminar_id`, `faculty_id` (UNIQUE pair), `kind` CHECK
(panel / attending).
**seminar_grades** — `seminar_scholar_id`, `grader_id` FK faculty (UNIQUE
pair), `scores` jsonb (`{criterion: score}`, validated against the rubric
snapshot), `rubric` jsonb (snapshot at grading time), `comment`,
`submitted_at`.
**todos** — `scholar_id` (indexed), `part` CHECK (introduction /
literature_review / methodology / experiments_results / discussion /
writing_presentation / other), `text`, `status` CHECK (open / done),
`source_seminar_scholar_id` FK (nullable), `done_at`, `created_by`.

### 3.4 Approvable items

Approval columns on every approvable table: `state` CHECK (`draft` /
`in_review` / `sent_back` / `approved`, default `draft`), `current_step` int
(NULL unless `in_review`), `chain_snapshot` jsonb (copied from
`approval_chains.steps` at submit), `submitted_at`, `approved_at`. CHECK
`ck_<table>_step`: `current_step IS NOT NULL` ⇔ `state = 'in_review'`. `approval_actions.at`
defaults to `clock_timestamp()` so several actions in one transaction still
order correctly. State
lives **only** in these columns and changes **only** through `workflow.py`.

**progress_reports** (APR) — `scholar_id` (indexed), `report_year` CHECK
2000–2100, `period` CHECK (January-June / July-December), `summary` +
approval columns. Partial unique `uq_apr_active (scholar_id, report_year,
period) WHERE deleted_at IS NULL` → 409 `duplicate_apr`.

**publications** (module `publications`) — `scholar_id`, `title`,
`authors`, `pub_type` CHECK (journal / conference / book_chapter / patent),
`venue`, `issn_isbn`, `indexing` text[] CHECK ⊆ {scopus, wos, ugc_care,
other}, `doi`, `pub_year`, `pub_status` CHECK (submitted / accepted /
published) + approval columns. `pub_status` is a bibliographic fact entered
by the scholar; it is **not** workflow state.

**thesis_submissions** (module `documents`) — `scholar_id`, `title`,
`plagiarism_tool`, `plagiarism_score` numeric(5,2) CHECK 0–100 (both writable
only by the Library step and required before it approves), `examiners` text
(Exam Office step; required before it approves; confidential — `thesis.py`)
+ approval columns. The final thesis and the plagiarism certificate are the
record's files (`files` owner `thesis_submissions`); submitting needs at least
one. Partial unique `uq_thesis_active (scholar_id) WHERE deleted_at IS NULL`
→ 409 `duplicate_thesis`. Final approval moves the scholar to Thesis
Submitted.

After approval (an approved item is immutable, so these are separate rows):
**examiner_reports** — `thesis_id` (indexed), `examiner_name` (confidential
until a viva is recorded), `institution`, `received_on`, `recommendation`
CHECK (accept / minor_revision / major_revision / reject), `notes`,
`released_at` (set when the Exam Office releases reports to the scholar and
supervisor). **vivas** — `thesis_id`, `held_on`, `venue`, `panel`, `outcome`
CHECK (pass / redefend / fail); a pass moves the scholar to Viva.
**shodhganga_deposits** — `thesis_id` (partial UNIQUE), `deposited_on`,
`handle_url`. Report, viva and deposit files hang off their own rows.

**no_dues_clearances** (module `documents`) — `scholar_id` + approval
columns; each step's approval is that office's confirmation of no dues
(default chain supervisor → department → library → research_office). Partial
unique `uq_no_dues_active (scholar_id) WHERE deleted_at IS NULL`.

**coursework_clearances** (module `coursework`) — `scholar_id`, `credits`
numeric(4,1) and `cgpa` numeric(4,2) (computed from graded enrolments at
submit; submit is refused below `settings.min_coursework_credits` /
`min_coursework_cgpa`, or with an ungraded course), `cleared_on` date (set
on final approval) + approval columns. Enrolments are frozen while a
clearance is in review or approved. Partial unique `uq_clearance_active
(scholar_id) WHERE deleted_at IS NULL`.

**approval_actions** — history of every chain action: `item_type`,
`item_id` (indexed pair; polymorphic, no FK — CHECK whitelist on
`item_type`), `step_index`, `step_kind`, `action` CHECK (submit / approve /
send_back / resubmit), `to_step` int (send-back destination; NULL = back to
initiator), `comment` (required for send_back — CHECK), `actor_id` FK users,
`at`. Written only by `workflow.py`.

### 3.5 Research record (modules)

**conferences** (module `conferences`) — `scholar_id`, `event_name`,
`event_type` CHECK (paper_presented / poster / attended / invited_talk /
workshop), `event_date`, `place`, `title`.

**documents** (module `documents`) — `scholar_id`, `title`, `doc_kind`
CHECK (proposal / chapter / synopsis / draft / other). Visible to the scholar
and their supervisor(s) only.
**document_versions** — `document_id` FK, `version_no` (UNIQUE per
document), `file_id` FK files (UNIQUE — one file is one version), `note`.
Append-only: files on a document cannot be removed.

**courses** (module `coursework`) — `unit_id` FK, `code`, `title`,
`credits` numeric(3,1) CHECK 0 < credits ≤ 20; UNIQUE `(unit_id, code)` among
live rows → 409 `duplicate_course`; a course with live enrolments cannot be
deleted.
**course_enrolments** — `scholar_id`, `course_id`, `semester`, `grade`,
`grade_points` numeric(4,2) CHECK 0–10; partial UNIQUE `(scholar_id,
course_id)`.

### 3.6 Administration (modules)

**admissions** (module `admissions`) — `candidate_name`, `email` citext,
`phone`, `unit_id` FK, `entrance_route` CHECK (net_jrf / gate /
university_test / other), `entrance_score`, `interview_date`,
`interview_result` CHECK (pending / selected / not_selected), `admitted_on`,
`scholar_id` FK (set when converted; UNIQUE; CHECK only when selected).
Scoped by `unit_id` (`scope.unit_predicate`). A converted admission can be
neither edited nor deleted.

**fellowships** (module `fellowships`) — `scholar_id`, `scheme` CHECK
(ugc_jrf / ugc_srf / csir / inspire / institute / other), `amount_monthly`
numeric(10,2), `hra_amount` numeric(10,2), `start_date`, `end_date`,
`srf_upgrade_on` (within the fellowship's dates), `status` CHECK (active /
completed / terminated); CHECKs `end_date >= start_date`, amounts ≥ 0. Scoped
by the scholar (`scope.scholar_predicate`).

**projects** (module `projects`) — `pi_id` FK faculty, `unit_id` FK (scope
anchor; defaults to the PI's unit), `agency`, `title`, `sanction_number`
(partial UNIQUE among live rows), `amount_sanctioned` numeric(12,2),
`start_date`, `end_date`, `status` CHECK (ongoing / completed / closed).
Scoped by `scope.project_predicate`: unit subtree, the PI, members.
**project_members** — `project_id`, `scholar_id` (any unit), `member_role`;
partial UNIQUE `(project_id, scholar_id)` among live rows.

**ledger_entries** (module `ledger`) — `project_id` FK nullable,
`fellowship_id` FK nullable, CHECK exactly one is set; `entry_kind` CHECK
(disbursement / expense), `head` CHECK (fellowship_salary / equipment /
consumables / travel / contingency / overhead), `amount` numeric(12,2) CHECK
> 0, `entry_date`, `reference`, `note`. Running balance = disbursements −
expenses in date order, computed on read (`grants.ledger_view`). Corrections
are a soft delete plus a new entry.
**utilisation_certificates** — `project_id`, `period_start`, `period_end`
(CHECK ordered), `submitted_on`; the signed certificate is attached through
`files` (owner `utilisation_certificates`).

### 3.7 Cross-cutting

**files** — `storage_key` (UNIQUE; `<table>/<record>/<file id>/<safe name>`),
`file_name`, `content_type` (allowlist in `app/files.py`: PDF, Office, images,
text/CSV, zip), `size_bytes` (CHECK > 0; the `MAX_UPLOAD_MB` cap is checked at
presign, and the size is signed into the upload URL), `etag` (from the bucket on
completion), `status` CHECK (pending / ready — `ready` only after the API has
confirmed the object exists at the declared size), `uploaded_by` FK users, owner
pair `(table_name, record_id)` with a CHECK whitelist that each phase widens by
migration (Phase 1: `scholars`; Phase 3 adds `publications`, `conferences`,
`documents`, `thesis_submissions`, `examiner_reports`, `vivas`,
`shodhganga_deposits`; Phase 5 adds `utilisation_certificates`). Visibility
is the owner record's
`get_or_403`. Soft delete keeps the object in the bucket (retention).

**comments** — flat threads; `(table_name, record_id)` polymorphic pair
(indexed, CHECK whitelist of commentable tables — scholars, meetings,
progress_reports, milestones, publications, conferences, documents,
thesis_submissions, coursework_clearances, no_dues_clearances), `author_id`, `body`
(1–4000 chars). Visibility = the target record's `get_or_403`.

**notifications** — `user_id` (indexed), `category` CHECK
(approval_waiting / sent_back / approved / apr_due / meeting_tomorrow /
fellowship_ending / grant_alert / seminar / system), `title`, `body`, `link`, `read_at`,
`email_status` CHECK (not_sent / sent / failed / muted), `email_error`,
`whatsapp_status` (same CHECK), `whatsapp_error`.

**audit_log** — every mutation on every table: `table_name`, `record_id`,
`action` CHECK (insert / update / soft_delete / restore / transition),
`from_state` / `to_state`, `prev` / `data` jsonb snapshots (password hashes
and token hashes redacted), `actor_id`, `actor_roles` text[], `at`. Written
only by `crud.py` / `workflow.py`. "Every mutation" means every record a person
creates or changes; operational rows are not audited: `notifications` (and
their read flag), `refresh_tokens`, `password_tokens`, `login_attempts`, SSO
login attempts, `job_runs`, and `approval_actions` (itself the approval trail,
alongside the item's `transition` row). A unit move audits the moved unit; its
descendants' paths follow from it.

**refresh_tokens** — `user_id` (indexed), `token_hash` (sha256; raw tokens
never stored), `expires_at`, `revoked_at`. Single-use, rotating.

**password_tokens** — set-password links: `user_id` (indexed), `token_hash`
(sha256, UNIQUE), `purpose` CHECK (invite / reset), `expires_at` (72 h),
`used_at`. Issuing a link marks every older unused link of that user used.

**sso_states** — one single sign-on attempt: `provider` CHECK (google /
microsoft), `state_hash` (UNIQUE), `nonce`, `code_verifier` (PKCE),
`expires_at` (10 min at start, then 60 s for the exchange), `callback_at`
(state spent), `user_id`, `exchange_hash` (UNIQUE; the one-time code handed to
the browser), `exchanged_at`.

**job_runs** — `job_name`, `run_date`; UNIQUE pair (daily job idempotency).

**login_attempts** — `email`, `at` (indexed pair). One row per failed login;
5 rows for an email inside 15 minutes → 429 (SECURITY.md §1). Rows outside
the window are inert.

## 4. Constraints & Invariants

- **One root unit** (`uq_org_root`); `path` always matches the parent chain.
- **Role scope shape** (`ck_role_scope`): unit roles need a unit; office
  roles never have one.
- **Duplicate items:** `uq_apr_active`, `uq_thesis_active`,
  `uq_clearance_active` → named 409s.
- **Workflow shape:** `current_step` set iff `in_review`; send-back needs a
  comment.
- **Unique identities:** `users.email`, `scholars.roll_number`,
  `org_units.code`, `projects.sanction_number` → named 409s via
  `errors.py` (psycopg `diag.constraint_name`).
- **Soft delete only;** every query filters `deleted_at IS NULL`.

## 5. Scope Anchors

Every scholar-owned record is scoped through its scholar: the scholar's
`unit_id → org_units.path` decides unit-head/admin visibility, the scholar's
`supervisor_id` (and `co_supervisor_id` when co-supervision is on) decides
supervisor visibility. Projects anchor on
`projects.unit_id`; faculty and admissions on their own `unit_id`. Index
`scholars(unit_id)`, `scholars(supervisor_id)`, GiST on `org_units.path`.

## 6. Search

Trigram GIN indexes on: users.full_name, scholars.roll_number,
scholars.research_title, org_units.name, progress_reports.summary,
meetings.agenda, milestones.resolution_number, publications.title,
publications.venue, projects.title. `GET /search?q=` ILIKEs across enabled
modules only, filtered by `scope.py`.

## 7. Migration Rules

1. Ship an Alembic migration in the same change — never raw SQL against a
   live DB.
2. Update this document in the same commit.
3. Verify with `alembic upgrade head` against a scratch DB; CI runs the full
   chain before every test suite.
4. Never break existing records — audit_log, approval_actions and
   soft-deleted history are the compliance trail.

## 8. Seed Data

`DATABASE_URL=… SEED_PASSWORD=… python -m app.seed` — idempotent
(`--reset-passwords` resets seeded accounts). Seeds: university tree
(Anveshan Demo University → School of Engineering {Computer Science,
Electronics}, School of Sciences {Physics, Chemistry}); root admin; research
office, exam office and library users; a HoD per department, a Dean per
school, a department admin; supervisors across designations (one HoD is also
a supervisor); scholars across stages with admission dates (one always about
four months from the UGC maximum, so the leadership view shows a scholar at
risk); every module enabled; a CSE course catalogue with one scholar's grades
(credits still short); a draft publication and a conference; a selected
admission candidate ready to convert; two fellowships (one ending in 60 days,
one upgraded to SRF), a CSE project with members, ledger entries and a
utilisation certificate. Approvable items are seeded as drafts
only — states move through `workflow.py`, not the seed. In production the
seed is replaced by a `--bootstrap` mode that creates only the root unit and
the root admin.
