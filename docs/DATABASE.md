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
on insert/move), `cross_unit_directory` bool (default false; set by the root
admin, opens the faculty and scholars directories to that unit's heads and
admins, SECURITY.md §3), `aishe_discipline` (nullable, 1–200 chars; the
discipline AISHE files the unit's Ph.D. scholars under, set by the root admin;
migration 0063), `notice_signers` text[] (who signs the unit's seminar
notices, in signing order; CHECK ⊆ exam_office / drc_secretary / admin / drc_chair /
unit_head / dean; null: admin, unit_head, dean — PRD F17b), `viva_notice_signers`
text[] (likewise for the unit's viva notices; null: exam_office, unit_head, dean;
migration 0049), `notice_names` jsonb (default `{}`, CHECK object; who signs the unit's
notices in a role several people hold — `{signer key: user id}`, for seminars and vivas
alike; migration 0052). A unit can be soft-deleted only when it has no live child
units, scholars or faculty.

**faculty_requests** — a request to faculty outside the sender's view: `kind`
(`seminar_panel`, `co_supervisor`), `seminar_id` or `scholar_id` (exactly the one
matching `kind`, CHECK), `email` citext as typed, `faculty_id` FK faculty (NULL
when the address matches nobody; the sender is not told), `requested_by` FK
users, `status` (`pending`, `accepted`, `declined`, `cancelled`), `note`,
`expires_at` (7 days; a pending row past it reads as expired), `responded_at`.
Not an approvable item: no chain, one answer.

**users** — login identity: `email` (citext, UNIQUE), `password_hash`
(NULL until the person sets one — invited or SSO-only accounts cannot log in
by password), `full_name`, `is_active`, `is_reviewer` (an external thesis reviewer,
closed everywhere but their reviews), `totp_secret` (the authenticator key, NULL until setup starts),
`totp_enabled_at` (NULL = not set up), `totp_last_step` (the last time step
used: a code works once), `recovery_hashes` text[] (sha256 of the unused
recovery codes), `email_muted` text[] (notification categories the
user muted for email; CHECK ⊆ categories in §3.7), `whatsapp_number` (NULL =
no WhatsApp; set only by the person themself, which is the opt-in; CHECK E.164
`^\+[1-9][0-9]{7,14}$`), `whatsapp_muted` text[] (as `email_muted`, for
WhatsApp), `privacy_notice_seen_at` (when the person last read the privacy notice;
migration 0066).

**signatures** — a person's specimen signature (PRD F17b): `user_id` FK users
(partial UNIQUE `uq_signatures_user`: one live row each), `content` bytea (PNG
or JPEG, 500 KB at most), `content_type`, `uploaded_by` FK users,
`confirmed_by` FK users + `confirmed_at` (CHECK `ck_signatures_confirmed`: both
or neither, and never the person themself). Usable for signing only once
confirmed. A new upload soft-deletes the old row. The bytes stay out of
`audit_log`.

**scholar_photos** — a scholar's photo (PRD F6): `scholar_id` FK scholars
(partial UNIQUE `uq_scholar_photos_scholar`: one live row each), `content`
bytea (PNG or JPEG, 500 KB at most), `content_type`. A new upload or a removal
soft-deletes the old row. The bytes stay out of `audit_log`.

**role_assignments** — `user_id` FK, `role` CHECK (`unit_head` / `admin` /
`research_office` / `exam_office` / `library` / `vice_chancellor` / `grievance_cell` /
`ombudsperson`; the last two since migration 0057), `unit_id` FK org_units.
CHECK `ck_role_scope`: `unit_head` and `admin` require `unit_id`; the four
office roles and the two grievance roles require `unit_id IS NULL` (university-wide). Partial unique
`(user_id, role, unit_id) WHERE deleted_at IS NULL`. An `admin` at the root
unit is the **root admin**. Scholar and supervisor are not rows here — they
come from the profile tables below.

**faculty** — `user_id` FK (UNIQUE), `unit_id` FK, `employee_id`,
`designation` CHECK (Professor / Associate Professor / Assistant Professor),
`max_scholars` (default from designation: 8 / 6 / 4), `can_supervise` bool
(default true). A faculty member with `can_supervise` holds the supervisor
role.

**scholars** — `user_id` FK (UNIQUE), `unit_id` FK, `roll_number` (UNIQUE),
`research_title`, `admission_date`, `study_mode` CHECK (full_time /
part_time), `gender` CHECK (female / male / transgender), `category` CHECK
(general / obc / sc / st / ews), `has_disability` boolean — these four
nullable, NULL = not recorded; the last three are personal data read only
through `scope.sees_personal` — `stage` CHECK (Registered / Coursework /
Proposal Approved / Pre-Synopsis / Thesis Submitted / Viva / Degree Awarded,
default Registered), `supervisor_id` FK faculty (indexed, nullable),
`co_supervisor_id` FK faculty (indexed, nullable; CHECK ≠ `supervisor_id`;
honoured only while `settings.co_supervision ≠ 'off'`; both mirror the open
`supervisor_appointments` row and change only through `app/supervision.py`),
`father_name` (nullable; personal data, as gender; migration 0042), `minority`
CHECK (none / muslim / christian / sikh / buddhist / jain / parsi), `nationality`
CHECK (indian / nri / pio / foreign) and `country` (1–100 chars; set exactly when
the nationality is nri, pio or foreign, `ck_scholars_country`) — all three
nullable = not recorded, personal data as gender, counted by the AISHE tables
(`app/returns.py`; migration 0063), `left_on` date +
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
`coursework`, `admissions`, `fellowships`, `projects`, `ledger`, `patents` — migration 0062),
`enabled`
bool, `updated_by`, `updated_at`. Seeded with every key; core features have
no row (always on).

**settings** — single row (`id` = 1, CHECK): `university_address` (default
''; the name is the root org unit's), `department_committee_name` (default
'Department Research Committee (DRC)', migration 0040: what the university calls
a department's research committee), `co_supervision` CHECK
(`off` / `view` / `approve`, default `off`), `require_hardcopy` bool (default
false), `require_no_dues` bool (default false: a thesis waits for an approved
no-dues clearance while true), `require_ethics` bool (default false: a thesis
waits for an ethics record while true), `require_two_factor` bool (default false: every password login needs an
authenticator code while true), `require_signing` bool (default false: every
approve and send-back needs a confirmed specimen signature and a fresh code
while true, PRD F17b), `apr_custom_template` bool (default
false) and `apr_sections` jsonb (ordered `[{"name", "hint"}]`, non-empty: the
university's own progress report sections, used only while the toggle is on), `seminar_graders` CHECK (`panel` / `panel_and_attending`, default
`panel`), `seminar_rubric` jsonb (ordered `[{"name", "max"}]`, non-empty),
`seminar_forms` jsonb (CHECK object; per seminar kind `{"marking": rubric |
questions, "form_name", "questions": [...]}`, PRD F15; a PATCH merges per kind),
`phd_forms` jsonb (default `{}`, CHECK object; per form of the PhD file —
enums.PHD_FORMS — any of `{"title", "number", "copy_to": [...]}`; a PATCH merges
per form and drops an emptied one; PRD F17 part 4, migration 0050), `date_format` text (default d_mon_yyyy, CHECK one of d_mon_yyyy / d_month_yyyy /
dd/mm/yyyy / dd-mm-yyyy / dd.mm.yyyy / yyyy-mm-dd / mm/dd/yyyy; how every date is written —
dates.py; migration 0053), `exam_controller_id` FK users (who signs every notice as Controller of Examinations when
several hold the Exam Office role; set by the Exam Office or the root admin; migration 0052),
`phd_index`
jsonb (default `[]`, CHECK array; the university's own index of the PhD file: rows
of `{"title", "sources": [...]}`, each source `annexure:<key>`, `form:<key>` or
`paper:<annexure>.<kind>` placed once — phd_index.py; empty: Anveshan's annexures;
migration 0051),
`min_coursework_credits` numeric(3,1) (default 12, CHECK 0–40) and
`min_coursework_cgpa` numeric(4,2) (default 5.5, CHECK 0–10),
`max_duration_years` (default 6, CHECK 3–12), `max_extension_days` (730),
`max_relaxation_days` (730), `max_maternity_leave_days` (240) — the UGC rule
values the university's ordinance sets; the thesis gates (migration 0056,
CHECK `ck_settings_thesis_gates`): `min_duration_years` (default 3, 0–6; 0 = no
minimum), `max_plagiarism_percent` numeric(5,2) (default 10, 0–100),
`min_publications` (default 0 = off, 0–10), `publications_indexed_only` bool
(default false); `publication_file_required` bool (default false; migration 0061: the paper
must be attached before a scholar submits a publication and before the Library verifies a
faculty one); `patent_verifier` (CHECK `research_office` / `library`, default
`research_office`; migration 0062: which office verifies patents); `grievance_appeals_to` (CHECK `ombudsperson` / `vice_chancellor`,
default `ombudsperson`; migration 0057: who decides a grievance appeal);
`updated_by`, `updated_at`.
University-wide switches that are not modules live here. Privacy (migration 0066): `privacy_notice` text (default '' = Anveshan's draft),
`privacy_notice_changed_at` (set whenever the text changes; everyone reads it again),
`privacy_officer_id` FK users (NULL: the root admins answer data requests).

**approval_chains** — `item_type` PK CHECK (`progress_report`,
`publication`, `coursework_clearance`, `thesis_submission`,
`no_dues_clearance`, `fellowship_claim`, `viva_arrangement`, `supervisor_change`), `steps` jsonb:
ordered array of `{"kind": …}` where kind ∈ `supervisor` / `department` /
`research_office` / `exam_office` / `library` / `vice_chancellor`; CHECK non-empty array (kinds
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
`notes`, `approved_title` (proposal approvals only: the latest approved one is
the thesis title, copied onto the live `thesis_submissions.title`), `seminar_id`
FK seminars (the registration / pre-synopsis seminar whose finalised review opened
the entry; partial unique `uq_milestone_seminar (scholar_id, seminar_id)`;
migration 0043).

**committee_formations** (committee versions, PRD F9b, migrations 0039-0040) —
whose committee: `scholar_id` (a Research Advisory Committee) or `unit_id` FK
org_units (a department's research committee), exactly one
(`ck_committee_formation_owner`), both indexed; `formed_on` date, `reference` (order
or resolution number), `notes`, `secretary_id` FK faculty (the supervisor when
it was formed: the secretary on an advisory committee's form; null on a
department's). The latest live row of a committee by `formed_on`, then
`created_at`, is the current committee; earlier ones keep
their members and roles frozen, only wording correctable (enforced in
`routers/committee.py`).

**committee_members** (members of a formation, PRD F9b) — `formation_id` FK
committee_formations (indexed; whose committee is read from it), `role` CHECK
(chairperson / secretary / member / vc_nominee, default member;
`ck_committee_member_role`: an advisory committee takes chairperson / member /
vc_nominee, a department's chairperson / secretary / member — enforced in
`routers/committee.py`), `seat` CHECK (hod / dean_nominee / faculty_nominee /
vc_nominee / scholar; department committees only, required there), then one of
`faculty_id` FK faculty (a member from this university), `scholar_member_id` FK
scholars (a scholar of that department, in the scholar's seat) — names and
units of both read live — or `name` + `institution` (an outside expert, with
`email` citext — required for new outside members, migration 0044):
exactly one kind (`ck_committee_member_kind`). Partial unique on live rows:
`uq_committee_member (formation_id, faculty_id)`, `uq_committee_scholar_member
(formation_id, scholar_member_id)`, `uq_committee_chair (formation_id) WHERE
role = 'chairperson'`, `uq_committee_secretary (formation_id) WHERE role =
'secretary'`. An advisory committee's secretary is the supervisor, never a row
here.

**supervisor_appointments** (Form IV, migration 0042) — one row per appointment,
kept for good: `scholar_id` (indexed), `faculty_id` FK faculty, `role` CHECK
(supervisor / co_supervisor), `appointed_on` + `order_ref` (the order;
nullable), `ended_on` (null = current; set to the day of the change when someone
else is appointed or the role is emptied; correctable afterwards on a past row). CHECK `ended_on ≥ appointed_on`;
partial unique `uq_supervisor_appointment_open (scholar_id, role) WHERE ended_on
IS NULL` on live rows. Existing supervisors were backfilled as open rows with no
order.

**supervisor_changes** (migration 0055; approvable, item type `supervisor_change`,
initiator the department admin; PRD F3) — `scholar_id` (indexed), `from_faculty_id` FK
faculty (nullable; the supervisor when proposed), `to_faculty_id` FK faculty, `from_name`
/ `to_name` (the names when proposed), `reason` (1–2000 chars), `scholar_consent` bool,
`order_ref`, `effective_on` date (the order's date; NULL = the day it is approved) +
approval columns. Partial unique `uq_supervisor_change_open (scholar_id) WHERE state <>
'approved' AND deleted_at IS NULL` — one change under way per scholar. On the final
approval the change is made through `app/supervision.py`: the open appointment ends and a
new one opens with this order and date.

**comprehensive_exams** (Form VI, migration 0042) — `scholar_id` (indexed),
`attempt` (CHECK ≥ 1; partial unique `uq_comprehensive_attempt (scholar_id,
attempt)` on live rows), `held_in` (the month: CHECK day = 1), `result` CHECK
(satisfactory / unsatisfactory), `notes`.

**ethics_clearances** (PRD F9c) — `scholar_id` (indexed), `kind` CHECK (human
/ animal / biosafety / not_required), `committee`, `approval_number`,
`approved_on`, `valid_until`, `notes`. `ck_ethics_fields`: `not_required`
carries only a non-empty `notes` (the reason); every other kind needs
`approval_number` and `approved_on`. `ck_ethics_dates`: `valid_until` ≥
`approved_on`. The certificate is a `files` row (`table_name =
'ethics_clearances'`).

### 3.3b Progress seminars (PRD F15)

**seminars** — `unit_id` FK (scope anchor), `kind` CHECK (progress /
registration / pre_synopsis, default progress), `title`, `starts_at`
timestamptz, `venue`, `report_due` date, `report_year`, `period` (all three
set exactly when `kind` = progress: `ck_seminars_report`), `notes`,
`notice` jsonb (the department admin's changes to this seminar's notice: any of
`signers`, `announcement`, `closing`, `copy_to`, and `names` — who signs in a role several
people hold; null: none — PRD F17b), `status` CHECK (scheduled / cancelled), `created_by`. Cancelling sets status;
rows are never deleted.
**seminar_scholars** — `seminar_id`, `scholar_id` (UNIQUE pair),
`hardcopy_received_on` date, `draft_points` jsonb (supervisor's working list
before finalising), `finalised_at`, `finalised_by`.
**seminar_panel** — `seminar_id`, `faculty_id` (UNIQUE pair), `kind` CHECK
(panel / attending).
**seminar_grades** — `seminar_scholar_id`, `grader_id` FK faculty (UNIQUE
pair), `scores` jsonb (`{criterion: score}`, validated against the rubric
snapshot), `rubric` jsonb (snapshot at grading time), `answers` jsonb +
`recommendation` (a kind marked by form questions: `[{"question", "answer":
yes|no, "remark"}]` in the form's order, and recommended /
recommended_with_changes / not_recommended; both or neither, CHECK; `scores`
and `rubric` are then empty), `comment`, `submitted_at`.
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
2000–2100, `period` CHECK (January-June / July-December), `summary`,
`sections` jsonb (ordered `[{"name", "text"}]`, default `[]`: the template's
sections as written, headings copied in), `assistantship` CHECK (with /
without; nullable = not stated; set by the actor at the current step, migration
0042) + approval columns. Files hang off it
(`files.table_name = 'progress_reports'`). Partial unique `uq_apr_active (scholar_id, report_year,
period) WHERE deleted_at IS NULL` → 409 `duplicate_apr`.

**publications** (module `publications`) — `scholar_id`, `title`,
`authors`, `pub_type` CHECK (journal / conference / book_chapter / patent),
`venue`, `issn_isbn`, `indexing` text[] CHECK ⊆ {scopus, wos, ugc_care,
other}, `doi`, `pub_year`, `pub_status` CHECK (submitted / accepted /
published) + approval columns. `pub_status` is a bibliographic fact entered
by the scholar; it is **not** workflow state.

**faculty_publications** (module `publications`; migration 0060) — `faculty_id` FK faculty,
the same paper columns and CHECKs as `publications` (`title`, `authors`, `pub_type`, `venue`,
`issn_isbn`, `indexing`, `doi`, `pub_year`, `pub_status`), no approval columns. `verification`
CHECK (waiting / returned / verified, default waiting), `return_note` (why it was returned; migration 0062 renamed it from `library_note`),
`checked_at`, `checked_by` FK users. `ck_faculty_publications_check`: waiting has no
`checked_at`; verified and returned have one, and returned has a note. Only
`faculty_papers.py` moves `verification`. Files hang off it (`files.table_name =
'faculty_publications'`). Trigram indexes on `title` and `venue`.

**patents** (module `patents`; migration 0062) — `faculty_id` FK faculty or `scholar_id` FK
scholars (`ck_patents_owner`: exactly one), `title`, `inventors`, `application_number`,
`filed_on` date, `office` (default in the form: Indian Patent Office), `patent_status` CHECK
(filed / published / granted), `published_on`, `granted_on`, `patent_number`
(`ck_patents_dates`: published needs `published_on`, granted needs `granted_on` and
`patent_number`, neither date before `filed_on`), and the same verification columns as
`faculty_publications` (`verification`, `return_note`, `checked_at`, `checked_by`;
`ck_patents_verification`, `ck_patents_check`). Only `verification.py` moves `verification`.
Files hang off it (`files.table_name = 'patents'`). Trigram index on `title`.

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
until a viva is recorded), `institution`, `origin` CHECK (national /
international; nullable, migration 0042, also on `thesis_reviews`), `received_on`, `recommendation`
CHECK (accept / minor_revision / major_revision / reject), `notes`,
`released_at` (set when the Exam Office releases reports to the scholar and
supervisor). **viva_arrangements** (migration 0041; approvable, item type
`viva_arrangement`, initiator the Exam Office) — `scholar_id`, `thesis_id`
(both indexed), `scheduled_at` timestamptz, `venue`, `online_link`, `notes`,
`invited_at` (when the external examiners were last emailed), `notice` jsonb (the
department admin's changes to this viva's notice, as `seminars.notice`; migration
0049) + approval columns. **viva_board_members** — `arrangement_id` (indexed), `role` CHECK
(chairperson / external_examiner / member), then `faculty_id` FK faculty or
`name` + `institution` + `email` (an outside person): exactly one kind
(`ck_viva_board_kind`; an external examiner is always outside — schema
validation). Partial unique on live rows: `uq_viva_board_faculty
(arrangement_id, faculty_id)`, `uq_viva_board_chair (arrangement_id) WHERE
role = 'chairperson'`. The supervisor always sits and is never a row.
**vivas** — `thesis_id`, `arrangement_id` FK viva_arrangements (the approved
arrangement it was held under; null only for vivas recorded before 0041),
`held_on`, `venue`, `panel`, `outcome` CHECK (pass / redefend / fail); a pass
moves the scholar to Viva.
**thesis_reviews** — one external reviewer on one approved thesis (PRD M3):
`thesis_id`, `reviewer_user_id` (set on accepting), `report_id` (the
`examiner_reports` row a submitted review became; its files move there too),
`name`, `email`, `institution`, `abstract`, `deadline`, `allow_download`, `status`
CHECK (invited / accepted / declined / expired / submitted), `invite_token_hash`
(single use, partial UNIQUE), `invite_expires_at`, `responded_at`,
`decline_reason`, `recommendation`, `submitted_at`. `uq_thesis_review_active`:
one live invitation per reviewer per thesis.
**thesis_review_comments** — `review_id`, `page` (CHECK >= 1), `body`.
**thesis_review_copies** — `review_id`, `code` (UNIQUE; random, holds no details),
`kind` CHECK (view / download). One row per copy handed out, so it is also the
view and download log. A lookup writes an `audit_log` row with action `lookup`.
**university_logos** — `content` bytea (PNG or JPEG, 500 KB at most),
`content_type`. The newest live row is in use; replacing or removing soft-deletes
the old one. Its own table so that reading `settings` never loads image bytes.

**provisional_certificates** — `thesis_id` (indexed; `uq_certificate_active`:
one unrevoked per thesis), `year` + `number` (UNIQUE, the per-year counter),
`serial` (`<university code>/PHD/<year>/<n>`), `verify_token` (UNIQUE, random,
redacted in `audit_log`), `issued_on`, `revoked_at` + `revoked_reason` (CHECK
both or neither). Revoked rows stay for good; a new certificate gets a new
serial and token.

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
`item_type`), `step_index`, `step_kind` (CHECK `ck_actions_step_kind`: supervisor /
department / research_office / exam_office / library / vice_chancellor / committee),
`action` CHECK (submit / approve /
send_back / resubmit), `to_step` int (send-back destination; NULL = back to
initiator), `comment` (required for send_back — CHECK), `rating` (NULL, or on an approve
of an assessed item: satisfactory / needs_improvement / unsatisfactory —
`ck_actions_rating`), `actor_id` FK users, `on_behalf_of` FK users (NULL, or
the supervisor when a stand-in or the head acted at the supervisor step),
`signature_id` FK signatures (the specimen that signed an approve or send-back
while signing was required, PRD F17b; NULL otherwise — kept even after the
person replaces their signature), `at`. Written only by `workflow.py`.

**supervisor_stand_ins** — who acts for a supervisor while they are away
(PRD F3): `faculty_id` FK faculty (the supervisor; one live row each,
`uq_stand_ins_faculty`), `stand_in_id` FK faculty (indexed; CHECK ≠
`faculty_id`), `starts_on`, `ends_on` dates (CHECK `ends_on >= starts_on`).
Active when today falls in the dates; ended early by soft delete.

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

**fellowship_claims** (module `fellowships`, migration 0033) — `scholar_id`,
`fellowship_id`, `month` date (its first day, CHECK), `leave_days` int CHECK
0–31 (default 0), `amount` numeric(12,2) ≥ 0 (fellowship + HRA for the month,
refreshed at every submit), `note` text + approval columns (item type
`fellowship_claim`). Partial unique `uq_fellowship_claim_month (fellowship_id,
month) WHERE deleted_at IS NULL`: one claim a month. Scoped through
`scholar_id` like every scholar record; never touches `ledger_entries`.

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
> 0, `entry_date`, `reference`, `note`, `confirmed_warnings` text[] (what the
person saved it despite: over_balance / over_sanction / future_date /
outside_period; server-written, default empty). Running balance =
disbursements − expenses in date order, computed on read
(`grants.ledger_view`). Corrections are a soft delete plus a new entry.
**utilisation_certificates** — `project_id`, `period_start`, `period_end`
(CHECK ordered), `submitted_on`; the signed certificate is attached through
`files` (owner `utilisation_certificates`).

### 3.7 Cross-cutting

**announcements** — the notice board (PRD F18; migration 0054): `unit_id` FK
org_units (null: the whole university; indexed), `title` (CHECK 1–200), `body`
(CHECK ≤ 5000), `pinned` bool, `ends_on` date (off the board after it), `posted_by`
FK users, timestamps, soft delete. Its file hangs off it in **files** (owner
`announcements`).

**grievances** — a scholar's grievance (PRD F19; migration 0057): `scholar_id` FK
(indexed), `category` CHECK (`supervision` / `evaluation` / `coursework` /
`fellowship` / `administration` / `other`), `subject` (CHECK 1–200), `description`
(CHECK 1–5000), `status` CHECK (`open` / `decided` / `closed` / `appealed` /
`appeal_decided` / `withdrawn`) — not an approvable item: its own lifecycle,
changed only by `grievances.py` — `due_on` date (the cell's deadline, then the
appeal's), `decision`, `decided_at`, `decided_by` FK users, `appeal_reason`,
`appealed_at`, `appeal_decision`, `appeal_decided_at`, `appeal_decided_by` FK
users, `closed_at`, timestamps, soft delete. Its papers hang off it in **files**
(owner `grievances`).

**data_requests** — a person's request about their own personal data (PRD F20;
migration 0066): `user_id` FK users, `kind` CHECK (`correction` / `erasure` /
`other`), `details` (1–3000 chars), `status` CHECK (`open` / `answered`), `reply`,
`answered_at`, `answered_by` FK users (CHECK `ck_data_requests_answer`: all three
set exactly when answered), timestamps, soft delete. `details` and `reply` are
redacted from `audit_log`.

**files** — `storage_key` (UNIQUE; `<table>/<record>/<file id>/<safe name>`),
`file_name`, `content_type` (allowlist in `app/files.py`: PDF, Office, images,
text/CSV, zip), `size_bytes` (CHECK > 0; the `MAX_UPLOAD_MB` cap is checked at
presign, and the size is signed into the upload URL), `etag` (from the bucket on
completion), `status` CHECK (pending / ready — `ready` only after the API has
confirmed the object exists at the declared size), `slot` (nullable; a named
place on a scholar's record — `employer_noc` / `entrance_minutes`, only with
`table_name = 'scholars'`, `ck_files_slot`; migration 0042), `uploaded_by` FK users, owner
pair `(table_name, record_id)` with a CHECK whitelist that each phase widens by
migration (Phase 1: `scholars`; Phase 3 adds `publications`, `conferences`,
`documents`, `thesis_submissions`, `examiner_reports`, `vivas`,
`shodhganga_deposits`; Phase 5 adds `utilisation_certificates`; migration 0045
adds `signed_copies`, whose files must be PDF, PNG or JPEG; 0057 `grievances`; 0060
`faculty_publications`; 0062 `patents`). Visibility
is the owner record's
`get_or_403`. Soft delete keeps the object in the bucket (retention).

**signed_copies** — the scan of a form signed on paper, standing for one entry of
the PhD file (PRD F17b; migration 0045): `scholar_id` FK scholars, `annexure`
(CHECK one of the file's annexure keys, `enums.PHD_ANNEXURES`), `record_id` (the
row behind the entry — a progress report, a seminar's scholar row, a committee
formation …; not a FK, it spans tables), `kind` (which of the entry's papers:
CHECK one of `enums.DOCUMENT_KINDS` — notification, report, attendance sheet, DRC
minutes, fee due creation, panel of examiners, the viva's papers …; default
`signed_copy`; migration 0046; `mark_sheet` added by 0047), `uploaded_by` FK users, `approved_by` FK
users + `approved_at` (set together, `ck_signed_copies_approved`). The scan is a
`files` row with `table_name = 'signed_copies'`, one per copy. The copy in use for
each paper of an entry is the newest with its scan ready; older ones stay as history. Index
`ix_signed_copies_scholar` (live rows).

**comments** — flat threads; `(table_name, record_id)` polymorphic pair
(indexed, CHECK whitelist of commentable tables — scholars, meetings,
progress_reports, milestones, publications, conferences, documents,
thesis_submissions, coursework_clearances, no_dues_clearances,
fellowship_claims), `author_id`, `body`
(1–4000 chars). Visibility = the target record's `get_or_403`.

**notifications** — `user_id` (indexed), `category` CHECK
(approval_waiting / sent_back / approved / apr_due / meeting_tomorrow /
fellowship_ending / grant_alert / seminar / notice / system / grievance; `grievance`
since migration 0059, and never in `users.email_muted` / `whatsapp_muted` — the API
refuses it), `title`, `body`, `link`, `read_at`,
`email_status` CHECK (not_sent / sent / failed / muted), `email_error`,
`whatsapp_status` (same CHECK), `whatsapp_error`.

**audit_log** — every mutation on every table: `table_name`, `record_id`,
`action` CHECK (insert / update / soft_delete / restore / transition / lookup),
`from_state` / `to_state`, `prev` / `data` jsonb snapshots (password hashes
and token hashes redacted; a grievance's words and its papers' file names stored as
"[redacted]", migration 0058 scrubbing earlier rows), `actor_id`, `actor_roles` text[], `at`. Written
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

**signing_codes** — an emailed code that signs one action on one item (PRD
F17b): `user_id` FK users, `item_type` CHECK (the item types), `item_id`,
`action` CHECK (approve / send_back), `code_hash` (sha256), `attempts` (5 wrong
tries end it), `expires_at` (10 min), `used_at`, `created_at` (indexed with
`user_id`: one code a minute). Sending a code marks the open ones for the same
user, item and action used.

**sso_states** — one single sign-on attempt: `provider` CHECK (google /
microsoft), `state_hash` (UNIQUE), `nonce`, `code_verifier` (PKCE),
`expires_at` (10 min at start, then 60 s for the exchange), `callback_at`
(state spent), `user_id`, `exchange_hash` (UNIQUE; the one-time code handed to
the browser), `exchanged_at`.

**job_runs** — `job_name`, `run_date`; UNIQUE pair (daily job idempotency).

**login_attempts** — `email`, `at` (indexed pair). One row per failed login;
5 rows for an email inside 15 minutes → 429 (SECURITY.md §1). Rows outside
the window are inert. A wrong authenticator code when signing counts under
`signing:<email>`, apart from logins.

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
publications.venue, faculty_publications.title, faculty_publications.venue, patents.title, projects.title. `GET /search?q=` ILIKEs across enabled
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
office, exam office and library users; a grievance cell member and an
Ombudsperson, with one open grievance from an ECE scholar; a HoD per department, a Dean per
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
