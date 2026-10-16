# Product Requirements Document

## 1. Product Overview

- **Product Name:** PhD Tracker
- **One-Line Description:** A supervisor–scholar workspace for Indian university PhD programs where UGC compliance paperwork is generated as a byproduct of daily use.
- **Product Type:** Vertical SaaS (per-university deployed instances)
- **Primary Platform:** Web (Next.js on Vercel; v1 was Frappe Desk)

## 2. Problem

**What problem are we solving?** The supervisor–scholar working relationship in Indian
universities runs on WhatsApp, email, and paper diaries. Meetings go unrecorded,
six-monthly progress reports (APRs) are copy-pasted the night before the deadline, and
RDC/DPGC approvals live in minute books nobody can search.

**Why does this problem matter?** UGC 2022 PhD Regulations (as amended March 2024)
require documented progress reviews, committee approvals, plagiarism gates, and
Shodhganga deposits. Universities face audits and NAAC/NIRF evidence demands with no
systematic record. Scholars suffer most: no documented trail means delayed approvals
and weak viva defense.

**How are users solving it today?** Existing products (Pegado, Unity, Assessfy,
Contineo) are administration/compliance tools the research office opens a few times a
year. Adoption is mandated, not wanted — the daily layer is still WhatsApp and Excel.

## 3. Goal

**Primary Goal:** Be the system supervisors and scholars open weekly (meetings,
feedback, progress reports) — adoption pulls itself instead of being mandated.

**Secondary Goals:**
- Every UGC compliance artifact (APR, milestone register, RDC trail) auto-generated
  with a defensible audit trail.
- Department-level sale (₹50k/year, approvable by a HoD) expanding institution-wide.

## 4. Target Users

### PhD Scholar
- **Description:** Registered research scholar, 3–6 year program.
- **Needs:** Documented meeting trail; feedback on drafts; proof of progress for RDC;
  visibility of what stage they're at.
- **Pain Points:** No record of supervisor interactions; progress reports written
  from memory; approvals opaque and slow.

### PhD Supervisor
- **Description:** Faculty member guiding 1–8 scholars (UGC caps: 8/6/4 by designation).
- **Needs:** One place for all scholars' meetings, drafts, and reports; minimal extra
  work — must produce paperwork they'd otherwise write by hand.
- **Pain Points:** Tracking scattered scholars; writing APR comments from memory;
  no view of where each scholar stands.

### Research Office Admin (daily operator)
- **Description:** Research office / DRC staff who maintain records and chase people.
- **Needs:** Overdue report flags; committee register; exports for audits.
- **Pain Points:** Chasing scholars manually; reconstructing records at audit time.

### Buyer (not a daily user): Registrar / Dean of Research / HoD
- **Description:** Approves the purchase; sees the system ~4×/year.
- **Needs:** Compliance evidence, audit trail, low cost. Gets PDFs and dashboards,
  **not a portal** (deliberate v1 decision).

## 5. User Stories

- As a **scholar**, I want to submit my six-monthly progress report in the system so
  that it's timestamped and my supervisor is notified.
- As a **supervisor**, I want to see all my scholars' reports pending my action so
  that I can approve or send back in one sitting.
- As a **supervisor**, I want to log each meeting's agenda, minutes, and action items
  so that the supervision trail exists without extra effort.
- As a **scholar**, I want to see my milestone history (proposal approval, pre-synopsis,
  viva) with resolution numbers so that I know exactly where I stand.
- As a **research office admin**, I want a list of overdue APRs per department so that
  I can chase the right people before the RDC meeting.
- As a **registrar**, I want to export every scholar's complete record as a PDF so
  that audit demands are met in minutes.

## 6. Core Features

### Feature 1 — Meeting Record
- **Purpose:** Log supervisor–scholar meetings (agenda, minutes, action items, next date).
- **User Flow:** Supervisor (or scholar) opens Meeting Record → selects scholar → fills
  minutes + action items → saves. Visible to both parties and research office.
- **Inputs:** scholar, supervisor, meeting_date, agenda, minutes, action_items,
  next_meeting_date.
- **Outputs:** Timestamped, versioned meeting trail on the scholar's record.
- **Acceptance Criteria:**
  - Both supervisor and scholar roles can create and read meeting records.
  - Record is immutable history (Frappe version log enabled).
  - Appears on scholar timeline (v1: list view filtered by scholar).
- **Edge Cases:** Scholar changes supervisor mid-program (old records stay linked to
  scholar); backdated entries allowed (real life) but visibly timestamped.

### Feature 2 — Six-Monthly Progress Report (APR) with approval workflow
- **Purpose:** The UGC-mandated progress report, digitized with a real approval chain.
- **User Flow:** Scholar creates APR (period Jan–Jun / Jul–Dec, year, summary) →
  submits → supervisor approves (doc becomes submitted; approved_on set) or sends back
  (with comment) → scholar revises and resubmits.
- **Inputs:** scholar, report_year, period, summary, supervisor_comment.
- **Outputs:** Submitted APR with audit trail; count toward compliance exports.
- **Acceptance Criteria:**
  - Only the scholar's role can move Draft→Submitted; only supervisor can
    Submitted→Approved/Rejected — enforced server-side by the workflow state
    machine (`services/api/app/workflow.py`); illegal moves → 422.
  - approved_on auto-set on approve.
  - One APR per scholar per (year, period) — hard constraint
    (`uq_apr_active` partial unique index → 409 `duplicate_apr`).
- **Edge Cases:** Scholar submits late period; supervisor changes before approval;
  scholar exits program mid-period (report remains for record).

### Feature 3 — Milestone register (RDC/DPGC approvals)
- **Purpose:** Record committee approvals with resolution numbers and dates.
- **User Flow:** Research office records milestone → fills approval body, resolution
  number/date, status → links to scholar.
- **Inputs:** scholar, milestone_type, status, approval_body, resolution_number,
  resolution_date, notes.
- **Outputs:** Scholar's milestone history; register exportable for RDC meetings.
- **Acceptance Criteria:**
  - Scholar sees own milestones read-only.
  - Supervisor and admin can create/update.
  - Milestone types cover UGC lifecycle: coursework, proposal approval, pre-synopsis,
    thesis submission, viva, degree awarded.

### Feature 4 — Scholar & supervisor directory
- **Purpose:** Who is registered, under whom, at what stage.
- **Acceptance Criteria:**
  - Roll number unique. Supervisor link with UGC cap displayed (8/6/4 by designation).
  - Stage tracked per scholar (Registered → … → Degree Awarded).

### Feature 5 — Compliance exports (v1 print formats; UGC-format pack is the wedge)
- **Purpose:** The feature that sells the system to the buyer.
- **Acceptance Criteria (v1):**
  - Frappe print format per APR (scholar + supervisor + dates).
  - Milestone register export per scholar / per department.
  - Full UGC-format pack: deferred until a pilot university supplies its formats.

## 7. Non-Goals

Intentionally NOT in this version:
- Admissions / entrance exam handling
- Coursework grading
- Research grant / ledger management
- Plagiarism-check API integration (scores recorded manually for now)
- NAAC/NIRF export packs, Shodhganga sync
- Git hosting or code review (GitHub activity mirroring is read-only, later)
- VC/HoD portals, committee member logins (they get PDFs/email)
- WhatsApp / Google Calendar integrations (legacy prototype had stubs; dropped)

## 8. MVP Scope

**Must Have:** Meeting Record; APR with approval workflow; Milestone register;
Scholar/Supervisor directory; roles; basic print formats.
**Nice to Have:** Overdue APR dashboard flags; per-scholar timeline page; duplicate
APR prevention.
**Future:** GitHub read-only mirror; UGC-format export pack; notification rules;
document versioning for drafts/thesis; per-university workflow configuration.

## 9. Success Metrics

**Primary (pilot):**
- One department, ≥10 scholars, ≥2 supervisors using it weekly for one full semester.
- ≥80% of APRs for the period submitted and approved inside the system (vs. ~0% baseline).

**Secondary:**
- Research office produces a RDC register export in <5 minutes.
- Zero "where is my approval" queries to the research office from pilot scholars.

## 10. Constraints

- **Technical:** Frappe v15 stack (Python 3.10–3.13, MariaDB, Redis); per-university
  deployment (universities want their own server); repo develops on an exFAT volume
  (AppleDouble junk — gitignored).
- **Business:** Solo developer, no funding; department-first pricing (₹50k/yr entry).
- **Design:** Stock Frappe Desk UI in v1 — no custom UI investment before pilot.
- **Timeline:** Pilot-ready within months, not years.

## 11. Assumptions

- UGC 2022 Regulations (amended 2024) remain operative through v1's life.
- A university's committee names (RDC/DPGC/DRC) vary but the milestone + resolution
  pattern is universal enough for v1's fixed milestone types.
- Supervisors and scholars have email accounts usable for Frappe logins.
- Manual plagiarism-score entry is acceptable until a pilot demands API integration.

## 12. Open Questions

- Pricing: per-scholar vs flat per-department? (Test with first pilot.)
- ~~Should duplicate (scholar, year, period) APRs be hard-blocked?~~
  Resolved in v2: partial unique index `uq_apr_active` → 409 `duplicate_apr`.
- Which university is the pilot? No commitment yet.
- Do print formats need per-university templates in v1, or one generic UGC format?
- GitHub mirror: fetch via API on schedule vs webhook? (Roadmap item 3; decide then.)

## 13. Definition of Done

- [x] Requirements implemented per feature's acceptance criteria (v2 core, Phases 0–3)
- [x] APR workflow verified by click-through with all three roles (Playwright,
      docs/TESTING.md — including immutability and the v1-gap regression)
- [x] Tests pass (`pytest` / `node:test` / `npm run build` — CI green)
- [x] App installs cleanly on a fresh database (`alembic upgrade head`; CI runs
      the chain on every push)
- [x] Security rules (SECURITY.md) satisfied
- [x] Documentation updated to match behavior