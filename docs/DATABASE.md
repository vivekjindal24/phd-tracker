# Database

## 1. Database Engine

- **Database:** MariaDB 10.6+ (managed by the Frappe/bench stack)
- **Hosting:** Per-university instance, site-local

## 2. Naming Conventions

Frappe conventions — do not invent your own:
- **DocTypes:** Title Case names ("PhD Scholar"); table is `tabPhD Scholar`
- **Fields:** snake_case (`report_year`, `resolution_number`)
- **Primary key:** `name` (DocType autoname — see below)
- **Links (FKs):** fieldtype Link with `options` = target DocType
- **Timestamps:** `creation`, `modified`, `owner`, `modified_by` — automatic

## 3. DocTypes

### PhD Scholar
- **Purpose:** Registered research scholar profile.
- **Autoname:** `field:roll_number` (the doc name IS the roll number)
- **Fields:** scholar_name* (Data), scholar_email (Data/Email), roll_number* (Data,
  unique), department (Data), admission_date (Date), supervisor (Link → PhD
  Supervisor), stage (Select: Registered / Coursework / Proposal Approved / Research
  Phase / Pre-Synopsis Done / Thesis Submitted / Viva Voce / Degree Awarded,
  default Registered), github_url (Data/URL)
- \* = mandatory

### PhD Supervisor
- **Purpose:** Faculty supervisor; UGC supervision cap reference.
- **Autoname:** `field:full_name`
- **Fields:** full_name*, email (Email), department (Data), designation (Select:
  Professor / Associate Professor / Assistant Professor), max_scholars (Int,
  default 8 — UGC cap 8/6/4), user (Link → User, optional login binding)

### Meeting Record
- **Purpose:** One supervisor–scholar meeting.
- **Autoname:** `MTG-{#####}`
- **Fields:** scholar* (Link → PhD Scholar), supervisor* (Link → PhD Supervisor),
  meeting_date* (Date), agenda (Small Text), minutes (Text), action_items
  (Small Text), next_meeting_date (Date)

### Progress Report
- **Purpose:** Six-monthly UGC progress report; submittable (doc_status).
- **Autoname:** `APR-{#####}`
- **Fields:** scholar* (Link), report_year* (Int), period* (Select: January-June /
  July-December), summary* (Text), supervisor_comment (Small Text), approved_on
  (Date, read-only, set by on_submit), workflow_state (added by workflow engine)

### PhD Milestone
- **Purpose:** Committee approval record (RDC/DPGC-style).
- **Autoname:** `MS-{#####}`
- **Fields:** scholar* (Link), milestone_type* (Select: Coursework Completion /
  Proposal Approval (RDC) / Pre-Synopsis Seminar / Thesis Submission / Viva Voce /
  Degree Awarded), status (Select: Pending / Approved / Rejected, default Pending),
  approval_body (Data, e.g. RDC / DPGC), resolution_number (Data), resolution_date
  (Date), notes (Small Text)

## 4. Relationships

- **PhD Supervisor → PhD Scholar:** one-to-many (scholar.supervisor Link).
  UGC cap check (count ≤ max_scholars) not yet enforced — validate() hook is the
  planned place.
- **PhD Scholar → Meeting Record / Progress Report / PhD Milestone:** one-to-many
  (child docs link back via `scholar`).
- **PhD Supervisor ↔ User:** optional 1:1 binding for login identity
  (`supervisor.user`).

## 5. Constraints

- **Required:** marked per field above (Frappe `reqd`).
- **Unique:** PhD Scholar.roll_number (`unique: 1`).
- **Link integrity:** Frappe enforces Link validity on insert; deleting a doc with
  dependents is blocked.
- **Not yet enforced** (deliberate v1 gaps — see PRD Open Questions):
  - duplicate (scholar, year, period) Progress Report
  - supervisor scholar-count ≤ max_scholars

## 6. Indexes

Frappe defaults: primary key (`name`), `modified`, and an index per Link field.
v1 access patterns (list by scholar, list by status/stage) are covered. Add custom
indexes only when a real list view measurably lags.

Desk global search: fields flagged `in_global_search` (scholar_name, roll_number,
full_name, summary, agenda, milestone_type, resolution_number, and the scholar links)
are indexed into Frappe's `__global_search` table; `install.py` registers the five
DocTypes in Global Search Settings so Desk search covers them. Fulltext tokenizes
hyphenated IDs unreliably — ID lookup goes through Link-field autocomplete / list
filters (LIKE queries), not the search bar.

## 7. Data Validation

- Select fields validate against their option lists (invalid option → error on save).
- Email/URL fields validate format (`options: "Email"` / `"URL"` on Data fields).
- All further business validation belongs in the DocType's `validate()`.

## 8. Soft Delete

Yes — standard Frappe behavior. Deleted docs are trashed (renamed to
`{name}-trash-{hash}`), restorable, and excluded from list views and exports.

## 9. Auditing

- `track_changes: 1` on all five DocTypes → full version history per document.
- Automatic `creation/owner/modified/modified_by` on every record.
- Workflow state transitions are themselves recorded (doc_status changes).
- This audit trail IS the compliance product — never disable versioning on these
  DocTypes.

## 10. Sensitive Data

- **Fields:** scholar_email, supervisor email, user link, thesis-adjacent content
  (minutes, reports), GitHub URLs.
- **Protection:** access only via authenticated Desk; role permissions below; export
  restricted to Research Office Admin. No data leaves the university's instance.

## 11. Migration Rules

Schema changes must:
1. Edit the DocType JSON in the repo (never via Desk UI alone — the file is the
   source of truth).
2. Ship a patch in `patches.txt` for any data migration (not just schema).
3. Be verified by installing on a fresh site AND migrating an existing one.
4. Never break existing production records (links, autonames).

## 12. Seed Data

None yet. Before the pilot, add fixtures: 2 supervisors, 3 scholars (one per early
stage), sample meeting/APR/milestone per scholar — doubles as the demo script and
test fixture. Track in the roadmap.

## Legacy prototype notes (from the removed Spring Boot attempt)

Ideas worth porting when the matching feature is pulled: `research_title` on
scholar, document versioning (fileName/version/uploadedAt), notification channels
(email/WhatsApp), `google_event_id` on meetings.