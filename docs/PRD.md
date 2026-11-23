# Product Requirements Document

> v3 rewrite (2026-10): the product grows from a supervisor–scholar PhD
> tracker into **Anveshan**, the central research system of a university —
> every level from scholar to the university's central offices logs in. The
> v2 rule "the buyer gets PDFs, never a login" is superseded.

## 1. Product Overview

- **Product Name:** Anveshan (Sanskrit: *exploration, inquiry*). Mascot: the
  clay owl (DESIGN_SYSTEM.md). Trademark check pending before first sale.
- **One-Line Description:** The one-stop research system for an Indian
  university — scholars, supervisors, departments, faculties and the central
  offices work in one place, and UGC compliance records fall out of daily use.
- **Product Type:** Vertical software, **one installation per university**
  (its own database and files).
- **Primary Platform:** Web (responsive; works on phones).

## 2. Problem

**What problem are we solving?** A PhD in an Indian university runs on
WhatsApp, email, paper diaries and Excel. Meetings go unrecorded, six-monthly
progress reports (APRs) are copy-pasted the night before the deadline, RDC/DPGC
approvals live in minute books nobody can search, publications are verified by
hand at thesis time, coursework grades sit in the exam office's spreadsheets,
and fellowship/project money is tracked in a separate ledger. Nobody above the
supervisor — HoD, Dean, research office, exam office, library — can see where
any scholar stands without phoning someone.

**Why does this problem matter?** UGC (Minimum Standards and Procedures for
Award of PhD Degree) Regulations 2022 require documented coursework,
six-monthly progress reviews by the Research Advisory Committee, committee
approvals, plagiarism checks and Shodhganga deposit. Universities face audits
with no systematic record; scholars suffer delayed approvals and weak viva
defence because their trail is scattered.

**How are users solving it today?** Existing products (Pegado, Unity,
Assessfy, Contineo) are administration tools the research office opens a few
times a year. Adoption is mandated, not wanted — the daily layer is still
WhatsApp and Excel.

## 3. Goal

**Primary Goal:** Be the system scholars and supervisors open every week —
and the single place every office above them looks — so adoption pulls itself
instead of being mandated.

**Secondary Goals:**
- Every level sees exactly its part of the university, live: a HoD their
  department, a Dean their faculty, the central offices the whole university.
- Every UGC artifact (APR, RDC register, coursework clearance, thesis
  submission trail) is produced with a defensible audit trail.
- Department-level entry sale expanding institution-wide; optional modules
  (§6.3) let each university switch on only what it needs.

## 4. Target Users

One login can hold **several roles** (a professor may be a Supervisor, the HoD
and the department admin at once); the dashboard combines them.

### Scholar
Registered research scholar, 3–6 year programme. Needs a documented trail of
meetings, feedback on drafts, proof of progress, and visibility of their
stage, coursework, publications and fellowship.

### Supervisor
Faculty guiding scholars (UGC caps: 8 / 6 / 4 by designation — Professor /
Associate / Assistant). Needs one place for all scholars' meetings, drafts and
reports; produces paperwork they would otherwise write by hand.

### Unit Head (HoD, Dean, …)
Heads any unit of the university's tree (department, faculty/school, …). Sees
every supervisor and scholar in their unit and everything below it; acts on
the department step of approval chains.

### Admin (scoped)
Manages people and structure **for one unit and everything below it** —
typically the department's PhD team head / DRC coordinator for a department.
At least one admin sits at the university root: the root admin also manages
the org tree, approval chains and modules.

### Research Office (central PhD office / Dean of Research's team)
University-wide. Final approval on progress reports, publications and thesis;
maintains the RDC/DPGC register; oversees admissions and grants.

### Vice Chancellor
University-wide (Decided 2026-11-10). Reads everything the Research Office
reads — every scholar, the leadership view, NAAC data, examiner names — and
enters no records. Decides only where an approval chain names the Vice
Chancellor step (F3); on a thesis that step is where they select the examiners
from the panel the Exam Office proposed (M3). Sees meeting minutes shared with
unit heads. The root admin appoints office holders in Settings.

### Examination Office
University-wide. Records coursework subjects and grades, clears coursework,
receives submitted theses and records examiners.

### Library
University-wide. Verifies publications (journal, indexing — Scopus / Web of
Science / UGC-CARE — DOI) and runs the thesis plagiarism check.

## 5. User Stories

- As a **scholar**, I submit my six-monthly progress report so that it is
  timestamped and moves up the approval chain without me chasing anyone.
- As a **supervisor**, I see every item waiting for my action across all my
  scholars and approve or send back in one sitting.
- As a **supervisor**, I log each meeting's agenda, minutes and action items,
  and choose who above me may read the minutes.
- As a **HoD**, I see every scholar in my department by stage, which APRs are
  overdue, which approvals are stuck, and each supervisor's load against the
  UGC cap.
- As a **Dean**, I see the same for every department in my faculty, side by
  side.
- As the **research office**, I give final approval on reports, publications
  and theses and keep the RDC register.
- As the **exam office**, I enter coursework grades and clear coursework.
- As the **library**, I verify a publication's indexing and record the
  thesis plagiarism score.
- As an **admin**, I add scholars and supervisors to my unit and assign
  supervisors.
- As the **Vice Chancellor**, I see the whole university on my home page and
  select thesis examiners from the proposed panel.
- As the **registrar**, I export any scholar's complete record as a PDF.

## 6. Core Features

### 6.1 Foundation

**F1 — Organisation tree.** The university is a flexible tree of units (e.g.
University → School → Department; some branches may skip levels). Each unit
has a name, a free-text kind label ("School", "Department", …) and a parent.
Scholars and faculty belong to a unit. Root admin edits the tree; units are
soft-deleted only when empty.

**F2 — People, roles and scope.** Users log in with email + password, or —
when the installation configures it — with their **university Google or
Microsoft account** (OpenID Connect). Single sign-on only matches an existing,
active account by verified email; it never creates accounts. So when IT
switches off a leaver's university account, that person can no longer log in
(an open session ends within the refresh-token lifetime). While the university setting `require_two_factor` is on, a password login
also needs a code from an authenticator app, set up at the person's first
login after the switch (SECURITY.md §1). New accounts get a
**set-password email** (single-use link, 72 h); **Forgot password** sends the
same link. Role assignments bind a user to a role and (for scoped roles) a
unit. Scope rule: a unit-scoped role sees its unit's subtree; supervisor sees their
supervisees; scholar sees self; the three offices are university-wide.
Acceptance: a HoD of Physics never sees a Chemistry scholar (403); a person
with two roles sees the union of both scopes, never more.

**F3 — Configurable approval chains.** Eight item types go through approval
chains: **progress report, publication, thesis submission, coursework
clearance, no-dues clearance, fellowship claim, viva arrangement, change of
supervisor**. The root admin configures one chain per item type **for the
whole university** (not per unit). Default chains:

| Item | Initiator | Chain |
|---|---|---|
| Progress report (APR) | Scholar | Supervisor → Department → Research Office |
| Publication | Scholar | Supervisor (authorship) → Library (journal, indexing, DOI) → Research Office |
| Coursework clearance | Exam Office (enters subjects + grades) | Department (confirms) → Exam Office (marks cleared) → Research Office (noted) |
| Thesis submission | Scholar | Supervisor → Department → Library (plagiarism score) → Exam Office (receipt, examiners) → Research Office (final) |
| No-dues clearance (when the university requires it, M3) | Scholar | Supervisor (lab dues) → Department → Library (books) → Research Office (fees) |
| Fellowship claim (module Fellowships, M6) | Scholar | Supervisor (certifies the month) → Department → Research Office |
| Viva arrangement (M3: Forms X and XI) | Exam Office (date, place, board) | Vice Chancellor |
| Change of supervisor (Decided 2026-11-22) | Department admin (new supervisor, reason, scholar's consent, order no. and date) | Department (HoD, never the proposer) → Research Office |

A scholar's **first** supervisor is appointed directly by the department admin. Once a
scholar has one, a different supervisor comes only through an approved **change of
supervisor**: the change happens on the final approval, from the order's date (else that
day); the old appointment is ended and kept in the supervision history; the old
supervisor, the new one and the scholar are told. One change can be under way per
scholar; it is refused at submit and at the final approval if the scholar's supervisor
has meanwhile changed or the new one has reached their UGC limit. Items already waiting
at the supervisor step move to the new supervisor by themselves.

"Department" step = the head **or** an admin of the scholar's own unit.
A chain may also carry a **Vice Chancellor** step (any holder of that role
acts); no default chain has one — the root admin adds it where the
university's ordinance wants the Vice Chancellor's decision.

**Delegation and escalation** (Decided 2026-11-13). No item waits on one
absent person:
- **Stand-in:** a supervisor names another supervisor of their own
  department, with a start and end date (at most 180 days), under My account.
  In those dates the stand-in approves or sends back at that supervisor's
  step and reads those scholars' records as the supervisor does; it ends by
  itself on the end date, or when the supervisor ends it.
- **Reminder at 7 days:** an item nobody has moved for 7 days is brought back
  to the people of its step; at the supervisor step that is the supervisor,
  the stand-in and the department's admins, with a note that a stand-in can
  be named.
- **Head steps in at 14 days:** after 14 days at the supervisor step the
  heads over the scholar's unit are told and may approve or send back in the
  supervisor's place.
- Whatever a stand-in or the head does is recorded and shown as done **on
  behalf of** the supervisor (item history and the report PDF). The other
  rules are unchanged: nobody acts on an item about themselves or on two
  steps in a row. Department and office steps need no stand-in: any head or
  admin at or above the unit, or any holder of the office role, may act.

Acceptance criteria:
- Only the actor of the current step may approve or send back — enforced
  server-side by the workflow engine; anyone else → 422 `workflow_violation`.
- On **send back**, the approver chooses the destination: back to the
  initiator, or to any earlier step; a comment is required.
- An item copies the chain at submit time (chain snapshot): editing a chain
  affects only items submitted afterwards.
- A fully approved item is immutable for every role.
- Every action records actor, step, comment and time (approval history +
  `audit_log`).

**F4 — Modules.** Core is always on (F1–F3, directory, meetings, progress
reports, RDC register, dashboards, search, notifications, exports). Optional
modules, switched by the root admin: **publications, conferences & talks,
documents & thesis, coursework, admissions, fellowships, research projects,
grant ledger.** A disabled module disappears from navigation and its API
returns 404 `module_disabled`.

**F5 — Notifications.** In-app inbox plus email (SMTP): item waiting for your
step, item sent back to you, item approved, APR due in 14 days / overdue,
meeting tomorrow, fellowship ending in 60 days. A user can mute email per
category; in-app is always on. Grievance notices (F19) cannot be muted, on email
or WhatsApp: they carry legal deadlines (Decided 2026-11-23). A notification is read once its person opens
the page it points to, however they got there, or acts on the item it is about
(from the item, the queue or anywhere else) — not only by clicking it in the
inbox (Decided 2026-11-19).

**WhatsApp** (Decided 2026-10-31; when the installation configures the Meta
WhatsApp Cloud API): each person may add their own WhatsApp number in
notification settings — adding it is the opt-in; only they can set or clear
it. Every notification then also goes to WhatsApp, mutable per category like
email. The message carries **only the kind of event and the link** (one
pre-approved utility template, e.g. "Anveshan: An item is waiting for your
approval. Open it: <link>") — never names, titles or content, so a mistyped
number leaks nothing and no record data passes through Meta. The outcome is
stored per notification (sent / failed with reason / muted / not configured),
like email.

### 6.2 Core daily use

**F6 — Directory.** Scholars (roll number unique, unit, supervisor, stage
Registered → … → Degree Awarded, admission date, research title) and faculty
(designation, unit, UGC cap displayed with current load). Over-cap
assignment → 409 `supervisor_cap_exceeded`. Visibility: a scholar sees their
supervisors, a supervisor their scholars and the faculty linked to them, heads
and admins their subtree; the root admin may open a department's directory to
the whole university (SECURITY.md §3). Faculty outside a sender's view are
reached by an emailed request they accept, for one seminar panel or co-supervision
(never thesis examiners, UX_FLOWS.md Flow 5b).

**Scholar profile** (Decided 2026-11-12). Each scholar also carries a study
mode (full-time / part-time), gender (female / male / transgender), category
(General / OBC / SC / ST / EWS) and whether they are a person with
disability; each may be left "not recorded". They arrive three ways: as
optional columns of the scholars import (F16); from the scholar, who is
prompted on Home to complete their own profile and may fill in any field
still not recorded (never change a recorded one → 409 `already_recorded`);
and from the admin over the scholar's unit, who alone corrects a recorded
value. The mode is seen by everyone who sees the
scholar and filters the scholars list. Gender, category and disability are
personal data: seen only by the scholar, the admins and heads over their unit,
the Research Office and the Vice Chancellor — not by supervisors or other
faculty — on the page, in the list and in exported files alike. They are
recorded only; no rule (duration, caps) reads them yet.

**Co-supervisor** (university setting `co_supervision`, set by the root
admin): `off` — none; `view` — a scholar may have one co-supervisor (any
faculty record, any unit — external co-supervisors are added as faculty; a
department admin picks only faculty they can see, and asks one from another
department by request)
who sees everything the supervisor sees and can log meetings, while only the
main supervisor acts on the Supervisor step; `approve` — as `view`, and the
co-supervisor may also act on the Supervisor step. Only the main supervisor
sets meeting sharing. Switching to `off` hides existing co-supervisor links
but never deletes them.

**F7 — Meeting record.** Supervisor or scholar logs date, agenda, minutes,
action items, next meeting date. Visible in full to both parties. **Private
by default to everyone above:** per meeting, the supervisor ticks who may read
the minutes — Unit heads / Research Office / Admins. Anyone in scope but not
ticked sees only that a meeting happened (date, scholar, supervisor). Backdated
entries allowed but visibly timestamped.

**F8 — Six-monthly progress report (APR).** Period Jan–Jun / Jul–Dec + year;
runs the APR chain (F3). One live APR per scholar per period
(409 `duplicate_apr`). Content (Decided 2026-11-10):
- **Sections:** a short summary plus one answer per section of the report
  template. Standard template: Work done this period, Progress against
  objectives, Difficulties faced, Plan for the next six months. University
  setting `apr_custom_template` (root admin, default off): while on, the
  university's own ordered list of sections (heading + hint, 1–10) is used
  instead; switching it off keeps their list for later. A draft may leave
  sections blank; submitting needs every section of the template in force
  written (422). A report keeps the headings it was written under.
- **Files:** the scholar attaches files (full report, slides, data) while the
  report is a draft or sent back; everyone who reads the report reads them.
- **Assessment:** an approver cannot approve bare. Each step gives a rating
  (Satisfactory / Needs improvement / Unsatisfactory) and written remarks
  (422 otherwise); both show in the history and print on the PDF. Sending back
  needs its reason, as for every item.
- **This period on record:** the page and the PDF show what the system already
  holds for the six months — supervision meetings held, the year's
  publications and the period's conferences (each only while its module is on). Its deadline comes from the scholar's progress seminar
(F15): "due soon" 14 days before the seminar's report due date, "overdue" after
it while still unsubmitted. No seminar scheduled → no deadline shown.

**F15 — Progress seminars (the six-monthly review).** Decided 2026-10-22.
- **Scheduling:** a unit head or admin schedules a seminar for their unit:
  title, date & time, venue or online link, **report due date**, the APR
  period it reviews (year + Jan–Jun/Jul–Dec), the **selected scholars** (from
  their subtree) and the **panel** (faculty from any unit). Editable and
  cancellable until it takes place.
- **Notifications** (in-app + email) on schedule, change and cancel: the
  selected scholars, their supervisors (and co-supervisors when on), the heads
  of the unit and of every unit above it (HoD, Dean), and the panel.
- **Hardcopy:** university setting `require_hardcopy`; when on, the department
  records "hardcopy received" per scholar.
- **Grading:** university setting `seminar_graders` = `panel` (named panel
  only) or `panel_and_attending` (plus any faculty who marks themselves
  attending). The **rubric** is a university setting: an ordered list of
  criteria, each with a maximum (one criterion = a single score; default:
  Progress, Presentation, Understanding, Plan — each out of 10). Each grader
  gives a score per criterion and a free-text comment per scholar.
- **Kinds of seminar** (Decided 2026-11-19): **progress** (the six-monthly
  review above, with its report period and due date), **registration** (the
  research proposal) and **pre-synopsis**; the last two review no report
  period. Universities mark these differently, so each kind is marked, per
  university setting `seminar_forms`, either by the **rubric** or by the
  university's **own form**: its name ("Form VII") and its questions, each
  answered yes or no with a remark, then a **recommendation** (recommended /
  recommended with changes / not recommended). Defaults: progress by rubric;
  registration and pre-synopsis by a generic form the university rewrites.
  One codebase, chosen per install: a university can be offered either or
  both.
- **Supervisor review:** once grading closes, the scholar's main supervisor
  opens the review. **AI** drafts to-do points from all graders' comments,
  each tagged with one standard part; the supervisor edits, accepts, rejects or
  adds points, then **Finalises**. Without AI configured the supervisor writes
  the points by hand — AI never blocks the flow.
- **Release:** on Finalise the scholar sees every grader's marks (per
  criterion, totals, average) and comments, and the accepted points join their
  **to-do list**; scholar and panel are notified.
- **To-do list:** per scholar, each point has its part, text, source seminar
  and status (open / done); the scholar ticks points done, the supervisor sees
  progress.
- **Standard parts:** Introduction, Literature review, Methodology,
  Experiments & results, Discussion, Writing & presentation, Other.
- **AI service:** one OpenAI-compatible connection (`AI_BASE_URL`,
  `AI_API_KEY`, `AI_MODEL`) — Gemini's free tier for cloud testing (demo data
  only: Google may use free-tier inputs), a local Ollama model in production.

**F9 — RDC / committee register (milestones).** Research Office (and scoped
admins) record committee decisions: milestone type (coursework, proposal
approval, RAC review, pre-synopsis, thesis submission, viva, degree awarded),
status (Pending / Approved / Rejected), approval body (RDC/DPGC/DRC/RAC),
resolution number and date, notes, and on a proposal approval the approved
title. A scholar's current RDC status is shown on
their profile and the head dashboards. **Order is enforced (2026-11-16):** a
stage can stand as Approved only when the stage before it in that list is
Approved (422 `stage_out_of_order`); Pending and Rejected entries are free.
A finalised registration or pre-synopsis seminar (F15) opens the matching
entry (proposal approval / pre-synopsis) as Pending, noting the panel's
recommendations and linking the seminar; the committee's decision is then
recorded on it (Decided 2026-11-19). Degree awarded is recorded as Approved only by the Research Office, and only
for a scholar with a supervisor, a recorded committee (F9b) and at least one
approved progress report (422 `award_not_ready`). Bulk import of past history
is not gated.

**F9b — Research Advisory Committee** (Decided 2026-11-10; versions and roles
2026-11-19). Each scholar has a committee, recorded as formations: each one a
version with the date it was formed and the order or resolution number. The
latest is the current committee; re-forming it (a new chair, say) records a new
version that starts as a copy of the current members, and the earlier one stays
as frozen history — the PhD file prints every version (F17). The supervisor is
always its Secretary & Member, shown automatically; the other members are
recorded per version, each with a role (Chairperson — at most one, Member, or
Member nominated by the Vice Chancellor) — faculty of this university (picked
from the directory) or an outside expert by name, institution and email (the
email shown only to those who keep the committee; Decided 2026-11-19). Members and
roles change only on the current version (409 `formation_superseded` on an
earlier one); any version's wording may be corrected — its date, order number
and notes, an outside expert's name or institution (an internal member's come
from the directory, 422 `directory_name`). Versions stay in date order (422
`formation_out_of_order`); a second chairperson is refused (409
`chairperson_taken`). An admin over the scholar's unit or the
Research Office keeps the list; the scholar, supervisor, heads above and the
Vice Chancellor read it. It shows on the scholar's page and prints on the
progress report PDF. A record only: membership opens no records and adds no
approval step, and outside members get no login (§7). The supervisor cannot be
added as a member (409 `supervisor_is_convener`); nobody twice in one version
(409 `duplicate_member`).

**Department research committee** (Decided 2026-11-19). Each department's
research committee (named by the university in Settings, default "Department
Research Committee (DRC)"; a DPGC elsewhere) is recorded the same way: dated
versions with their order number, re-constituted as a copy of the current
members, earlier versions frozen but correctable in wording. Each member has a
role — Chairperson, Secretary (at most one each; 409 `chairperson_taken`,
`secretary_taken`) or Member — and a seat: Head of the Department (ex officio),
Dean's nominee, faculty nominated by the department, Vice Chancellor's nominee,
or a PhD scholar of the department (only a scholar of that department or below
sits there, 422 `scholar_not_in_unit`; 422 `seat_mismatch` / `role_not_allowed`
otherwise). An admin over the department or the Research Office keeps it;
anyone who can see the unit reads it (a scholar, only their own department's).
It names the Chairperson and Secretary on the department's notices and forms
and prints as its own page in the PhD file (F17).

**F9c — Research ethics clearance** (Decided 2026-11-10). Per scholar, an
admin over their unit or the Research Office records either one or more
clearances — kind (human ethics / animal ethics / biosafety), committee,
approval number, approval date, valid-until date and the certificate file — or
that **none is required**, with the reason. A clearance and "not required"
cannot stand together (409 `ethics_conflict`). The scholar, supervisor, heads
above and the Vice Chancellor read it on the scholar's page. The daily job
tells the scholar and supervisor 60 days before a clearance lapses. University
setting `require_ethics` (default off): while on, a thesis cannot be submitted
until the scholar has an ethics record → 409 `ethics_pending`. A lapsed
clearance still counts: it covered the work when the work was done. A record,
not an application: the ethics committee decides outside the system.

**F10 — Dashboards.** One home page per user, combining their roles:
- Scholar: stage, next APR due, items in progress and where, coursework
  status, publication count, fellowship end date, next meeting.
- Supervisor: my queue, scholars by stage, overdue APRs, load vs UGC cap.
- Unit head: subtree overview — scholars by stage, overdue APRs, items stuck
  > 14 days at any step, supervisor load vs cap, publications this year; a
  Dean also gets a per-unit breakdown.
- Offices: their queue (items at their step), oldest first.
- Admin: people and setup gaps in their unit (scholars without supervisor,
  units without head).
- Grievance cell / Ombudsperson (or the VC, where appeals go to them): grievances
  to decide, with how many are past the deadline or the next deadline; someone
  holding only a grievance role sees no approval tile. Vice Chancellor:
  grievances past their deadline, university-wide, when any are. Scholar: a
  tile when their grievance has a decision to accept or appeal (Decided
  2026-11-23).

**F11 — Scholar timeline.** One page per scholar: meetings, reports,
milestones, publications, coursework, thesis — in date order, each item
filtered by the viewer's permissions.

**F11b — Audit log** (Decided 2026-11-11). A page for the root admin, Research
Office, Vice Chancellor and scoped admins listing every recorded action,
newest first: when, who (with their roles), what happened, the kind of record,
the scholar it concerns and, for a change, which fields changed. Filters:
scholar, kind of action, kind of record, date range. It never shows a record's
contents (SECURITY.md §3).

**F12 — Search.** Partial-match search over names, roll numbers, titles,
resolution numbers; results scoped exactly like the lists.

**F13 — Comments & files.** Flat comment threads and file attachments on any
record, visible exactly when the record is. Files live in S3-compatible object
storage; upload cap configurable (default 100 MB — theses are large).

**F14 — Exports.** APR PDF, RDC register PDF/CSV, scholar complete-record
PDF, the PhD file (F17), unit summary PDF (heads). Anyone may export what they can see. PDFs stay
print-like and readable in grayscale.

**F16 — Bulk import.** Decided 2026-10-24. So that a department starts with
its real data, not an empty system. An admin uploads an Excel (.xlsx) or CSV
file built from a downloadable template, one sheet/file per kind:
- **Faculty:** name, email, designation, unit, UGC cap (blank = designation
  default).
- **Scholars:** roll number, name, email, unit, supervisor email,
  co-supervisor email (only when co-supervision is on), stage, admission date,
  research title, and optionally mode, gender, category, person with
  disability (a blank stays "not recorded").
- **History (RDC register):** roll number, milestone type, status, approval
  body, resolution number, resolution date, notes.

Acceptance criteria:
- **Dry run first:** every row is validated and the admin sees per-row errors
  (row number, column, reason) and a count of what would be created. Nothing
  is written until the admin confirms.
- **All or nothing:** a confirmed import runs in one transaction; any error →
  nothing is written.
- **Same rules as the forms:** units must lie in the admin's subtree,
  supervisor caps hold (409 `supervisor_cap_exceeded` becomes a row error),
  roll numbers and emails stay unique.
- **Safe to re-run:** rows whose email / roll number already exists are
  reported as "already present" and skipped, never overwritten.
- Each created record writes its `audit_log` row; imported people get the
  set-password email (F2) only when the admin ticks "send invitations".

**F17 — The PhD file** (Decided 2026-11-18). Universities keep one paper file
per candidate: an index of annexures, then every form, circular, attendance
sheet, report and certificate from admission to award, typed again on each form
and filed by hand. Anveshan generates that file as one PDF per scholar, on
demand, from what is already recorded.
- **Index first:** S. No., annexure, date, page. Annexures follow one fixed
  order, the order of the career: admission and entrance record (M5); employer
  NOC (upload, for employed candidates); supervisor and co-supervisor
  appointment; advisory committee formation, every version (F9b); coursework,
  grades and clearance (M4); comprehensive examination report; registration
  seminar; committee decisions (F9); each period's progress report and progress
  seminar (F8, F15); publications and conferences with their certificates (M1,
  M2); pre-synopsis seminar; thesis submission, plagiarism score, no-dues and
  fee (M3); examiner panel, invitations, acceptances and reports; corrections
  made for the examiners; viva — approval to hold it, the board, the notice,
  attendance and the report; provisional certificate and Shodhganga deposit;
  copies of the thesis, synopsis and registration seminar report.
- **Each annexure** is a form generated from the record, an uploaded scan, or
  both (see F17b). An annexure with nothing recorded is listed in the index as
  "Not on record", never left out silently.
- **Seminars and the viva** each get a generated circular (date, time, venue,
  scholar, topic, signatories, "copy to" list) and a pre-filled attendance sheet
  (scholar, topic, date, blank rows to sign) to print; the signed sheet is
  scanned back in. *Built:* the seminar circular — one page per scholar, signed
  by hand by the department admin, the HoD and the Dean by default (owner,
  2026-11-21). The department admin changes who signs for every seminar of the
  department, and who signs, the announcement, the closing line and the "copy
  to" list for one seminar; the seminar's attendance sheet (the announcement and
  the scholar's details, then rows already naming the supervisor, the panel and
  the scholar, and blank rows to sign — 18 in all) — **Download attendance
  sheet** on the seminar, and in the PhD file after the seminar's report. Once a
  seminar paper's signed scan is approved, the signed PhD file carries the scan in
  place of its generated page (owner, 2026-11-21). *Built:* the viva's notice
  (with the examination board) and attendance sheet, from the arrangement:
  signed by the Controller of Examinations, the HoD and the Dean by default,
  changed by the department admin as for seminars. A notice never guesses a
  signatory: a role several people hold is named only once chosen — by the
  department admin, and for the Controller of Examinations once for the whole
  university by the Exam Office or the root admin (owner, 2026-11-22);
  **Download notice** on the seminar for those who run it, and in the PhD file
  before the seminar's report.
- **Names are the university's:** each annexure's title and form number (e.g.
  "Form V — Formation of RAC") is a university setting with a plain default, as
  the certificate wording is; the "copy to" list of circulars likewise.
  *Built:* **Settings → Forms of the PhD file** — each of the 18 generated forms
  takes the university's title, form number (printed at the top right) and
  "copy to" list; empty keeps Anveshan's. A notice's list can still be changed
  for one seminar or viva by the department admin. *Built:* **Settings → Index
  of the PhD file** — the university writes its own index (e.g. Medi-Caps' 30
  rows), each row filled from a whole annexure, one generated form with its
  signed scan, or one uploaded paper; a row with none prints "Not held in
  Anveshan". The printed file follows it; what no row takes follows the rows
  under Anveshan's headings, so no record is left out. Screens keep Anveshan's
  annexures. The index runs onto as many pages as it needs.
- **Who:** anyone who may read the scholar's whole record generates it; what
  they may not read is left out exactly as on screen (examiner names before the
  viva, unshared meeting minutes — SECURITY.md §3). Signed scans are uploaded by
  an admin over the scholar's unit or the Research Office.
- **Needs, built with it:** seminar types (registration / progress /
  pre-synopsis); advisory committee roles (chairperson, member, VC nominee,
  secretary), formation date and history; the department committee's
  membership; viva arrangements (approval to hold it, board, examiner invitation,
  notice, report); supervisor appointment date and reference number; national /
  international examiner; comprehensive examination attempt and month; the "may
  continue with / without assistantship" line on the progress report.
- **The small records, as built (2026-11-19):**
  - *Supervision history* (Form IV): every appointment of a supervisor or
    co-supervisor is kept — who, the date and order number appointing them, and
    when it ended. Changing the supervisor ends the current appointment (dated
    the day of the change) and opens a new one, so whoever guided the scholar
    stays on record. The admin over the scholar's unit records or corrects the
    order on any appointment, past or current, and the end date of a past one
    (on or after it began, not in the future; a current appointment ends only by
    appointing someone else — 422 `appointed_after_end`, `end_in_future`,
    `appointment_current`, `end_required`); anyone who reads the scholar reads
    the history.
  - *Father's name*: on the scholar's profile, personal data like gender (the
    scholar fills it once, the admin corrects it).
  - *National / international* on each examiner report and reviewer invitation
    (optional; carried over when a review becomes a report).
  - *Comprehensive examination* (Form VI): numbered attempts, each with the
    month held and its result (satisfactory / unsatisfactory), kept by the admin
    over the unit or the Research Office. Attempts stay in date order (422
    `attempt_out_of_order`); none after a satisfactory one (409
    `comprehensive_passed`); only the latest is removed (409 `not_latest_attempt`).
  - *Assistantship line*: "may continue with / without assistantship", stated on
    a progress report by whoever acts at its current step, printed on its PDF.
  - *Admission papers*: named places on the scholar's record for the employer's
    no-objection certificate and the entrance-examination minutes, added by the
    admin over the unit.
- **The file, first cut (2026-11-19):** "Download PhD file" on the scholar's
  page. Page 1 is the index: every annexure in the order above with its first
  date, "Signed" / "Unsigned" (approved items: every approval carries a
  signature or not) and its page — or why it has none: "Not on record", "Not
  shown to you" (the caller's role does not read that part, as on screen), "Not
  in use at this university" (its module is off). Each recorded annexure then
  starts a new page with a plain summary of its entries. *Forms (2026-11-20):*
  entries the university keeps a paper form for print as that form, one page
  each, after the university's own layout (Medi-Caps Form IV–VIII): the
  scholar's particulars, the body (members, courses and attempts, the panel's
  answers), the signature block, "Forwarded to the Dean of the Faculty" and
  "Copy to". So far: appointment of supervisor, formation of the advisory
  committee, comprehensive examination, registration seminar report,
  pre-thesis synopsis report, coursework clearance, submission of the thesis,
  approval for the viva with the constitution of the examination board (Form X
  and XI on one page) and the viva-voce examination report. A form approved in
  the portal carries its approval record (each action, by whom, when) and its
  approvers as signers, with the specimen each signed with. "Download PhD file" asks signed or unsigned:
  signed prints the specimens of those who signed in the portal and the
  approved scans; unsigned prints the forms alone with signature and date
  lines, for signing by hand. Each part is read
  through the same rule as its screen: examiner names stay withheld before the
  viva and unreleased reports out of the scholar's copy; outside members'
  emails and personal data are not printed. Still to come: the forms
  themselves, uploaded scans merged in, circulars and attendance sheets, the
  university's own annexure titles; "corrections made for the examiners" has
  no record of its own yet and is not listed.

**F17b — Signatures on forms** (Decided 2026-11-18). A wet signature stays the
legal proof; the electronic approval is the record of it.
- **Every generated form carries, at its foot, the electronic approval
  record:** each step's approver, their role, the action and its date and time,
  from the approval chain and the audit log (F3, F11b). Forms with no approval
  chain carry who recorded them and when.
- **And a wet-signature block** for each signatory the form names (supervisor,
  committee members, chairperson, Dean …), to be signed on paper.
- **Signed scan:** the signed paper is scanned and uploaded against that
  annexure. In the file, the signed scan stands in place of the generated form;
  the generated form stays downloadable. The index marks each annexure "signed"
  or "unsigned", so a missing signature shows.
  *Built (owner, 2026-11-19):* "Signed copies of forms" on the scholar's page
  lists every entry of the PhD file; for each, the scholar's supervisor, the
  department admin or the Research Office uploads the scan (PDF or photo). The
  admin's and the Research Office's uploads count at once; a supervisor's waits
  until the department admin or the Research Office approves it, and they are
  notified. Every upload, approval and removal is in the audit log. An approved
  copy marks its entry signed, and in the downloaded PhD file its pages follow
  the entry. A new upload replaces the copy in use; the old one stays on record.
  *Every paper of the file has a place (owner, 2026-11-19)*, after the
  university's own 30-document index: each entry holds its own papers —
  a seminar its notification, report and attendance sheet; a committee
  decision the DRC minutes and the notice of the DRC chairperson; the thesis
  submission its signed form, the examination fee due creation and the
  modifications made at the examiners' request; the viva arrangement its
  approval, the constitution of the board, the notification and the email to
  the viva examiner; the viva its report and attendance sheet; every other
  entry one signed copy. A separate entry, "Panel of examiners and letters with
  the examiners", holds the panel and the emails to and acceptances from the
  national and international examiners; only the Research Office, the Exam
  Office and the department admin see and handle it. One copy per paper: two
  national examiners' letters go in as one PDF.
  *Coursework mark sheet (owner, 2026-11-20):* the coursework annexure's
  "Courses and grades" holds the mark sheet. The exam cell uploads it (the
  department admin and the Research Office may too) and it counts at once; a
  scholar may upload their own, which waits for the department admin's
  approval.
- **The signature is the main mark** (stakeholder requirement): on a generated
  form each signatory's signature stands where their wet signature would, with
  the electronic approval record below it as detail.
- **Signed or unsigned copy** (owner, 2026-11-19): downloading a form that
  carries signatures first asks "Download signed or unsigned?". Signed prints
  the signatures on record; unsigned leaves them out and gives a signature and
  date line for each signatory, so the printed copy is signed by hand and its
  scan uploaded. Live on the progress report (the scholar and the advisory
  committee, or the supervisor when no committee is recorded); the PhD file's
  forms follow in its next part.
- **Signing inside the portal** (Decided 2026-11-18): an approval is a
  signature, not a click — a session left open on a shared computer must not
  be enough. Each signer keeps a **specimen signature**, a scan or phone photo
  of their wet signature, given in one of two ways: they upload it themselves
  and an admin over their unit or the Research Office confirms it before it
  can be used — the admins of the nearest unit above them are notified, else
  the Research Office; or they sign on paper at their department and that admin or
  the Research Office uploads it for them, which confirms it. A new
  specimen goes through the same again. Every approve, send-back or reject —
  and every form a person signs — asks for a **fresh code**; a code that does
  not match signs nothing. The code comes from the signer's authenticator app
  (Microsoft Authenticator, Google Authenticator or any standard app) when they
  have set one up, otherwise it is **emailed** to them: six digits, valid for
  ten minutes, usable once and only for the action it was sent for; five wrong
  codes end it and a new one must be sent. Without email configured (F5),
  signing needs the authenticator app. The specimen is stamped on the form
  with the signer, time and step, and the signing is audited. A university
  setting, off by default (the demo) and switched on for a live install;
  while it is on, nothing is approved in bulk from the queue. While it is off,
  an approver whose specimen is confirmed may still choose to sign a decision
  (the same fresh code); otherwise the decision carries no signature
  (Decided 2026-11-19). Later, when a
  university asks: a code by text message, and Aadhaar eSign.

**F18 — Notice board** (Decided 2026-11-22). Notices for the whole university
or for one department — a fee notice, a seminar week, a holiday — each with a
title, text, an optional file (e.g. the fee notice as a PDF), an optional
"take it down after" date and a pin. The Research Office and the root admin
post anywhere; a department admin posts to their unit and the units inside it.
A university notice reaches everyone; a department notice reaches that
department's scholars, faculty, heads and admins (and those of the units inside
it) and the heads and admins above it; the offices and the root admin read every
notice. Everyone it is for is told in the portal and by email (category
"notice", which each person may mute). Home shows the latest three; **Notices**
lists current and past ones. Every post, edit and removal is audited.

**F19 — Grievances** (Decided 2026-11-23; UGC Redressal of Grievances of Students
Regulations, 2023). A scholar raises a grievance (about supervision, evaluation,
coursework, fellowship, administration or other: subject, what happened, papers
attached). The **grievance cell** (a university-wide role the root admin gives
to the committee's members) decides it, with reasons, within 15 working days
(Saturdays and Sundays skipped; holidays are not known). The scholar accepts, or
appeals within 15 days; unappealed, it closes. The appeal goes to the
**Ombudsperson** (a role of its own), or to the Vice Chancellor where the root
admin has chosen so, who decides within 30 days. The scholar may withdraw it
while it is with the cell. Read only by the scholar, the cell and the Vice
Chancellor, and by the appeal's decider once appealed — never by the supervisor
(even one sitting on the cell), heads, admins, other offices or the root admin —
unless the root admin appoints themselves to a grievance role, which the audit log
records.
Notifications and emails say only that there is a grievance, never its words.
The daily job reminds whoever must decide 3 days before the deadline and tells
them and the Vice Chancellor the day after it is missed. A sexual-harassment
complaint is pointed to the Internal Complaints Committee, outside Anveshan.
The list puts grievances still to be decided first, soonest deadline on top;
Home shows each role what waits on them (F10); grievance notices cannot be
muted (F5).

### 6.3 Optional modules

**M1 — Publications** (chain). Title, authors, type (journal / conference /
book chapter / patent), venue, ISSN/ISBN, indexing (Scopus / WoS / UGC-CARE /
other / none — multiple), DOI, year, status (submitted / accepted /
published), file. Library verifies indexing at its step. **Fill in from the
DOI** (Decided 2026-11-22): the scholar pastes a DOI (or its doi.org link) and
the form fills title, authors, type, venue, ISSN/ISBN and year from Crossref's
public API; the scholar checks and saves as usual, and is told if they have
already recorded that DOI. Indexing is never filled (Crossref does not know
it). Only the DOI is sent out; no key is needed. **Import from ORCID**
(Decided 2026-11-23): the scholar gives their ORCID iD (checked against its
check digit); their public works are listed, and the chosen ones with a DOI
(up to 50 at a time) are filled from Crossref and saved as drafts. A DOI
already recorded, unknown to Crossref, or missing authors, venue or year is
skipped with the reason; a work without a DOI is added by hand.
**The paper file** (Decided 2026-11-23) is optional unless the university asks
for it: with Settings → UGC rules "Require the paper file" on, a scholar cannot
submit (or resubmit) a publication without it → 422 `workflow_violation`, and
the Library cannot verify a faculty paper without it → 422 `file_required`.
**Faculty publications** (Decided 2026-11-23): any member of faculty (a faculty
record, whatever role they hold) records their own papers the same way — by
hand, from a DOI, or from ORCID. There is no chain: each goes straight to the
Library, which corrects indexing and DOI and **verifies** it, or **returns** it
with a note saying what to correct; the corrected paper goes back to the
Library. A verified paper is locked; the Library may return it for a later
correction. The author may remove one not yet verified; the Library never
verifies its own. Read by the author, the Library, the Research Office and the
Vice Chancellor, and heads and admins over the author's unit. The Library is
told of each new or corrected paper (one notice for an ORCID import), the
author when it is verified or returned; Home shows the Library what waits and
the author what came back. Only verified, published faculty papers count in
the NAAC sheets (M9), alongside scholars' approved ones.

**M2 — Conferences & talks.** Event, type (paper presented / poster /
attended / invited talk / workshop), date, place, title, certificate file.
Recorded by the scholar, visible upward; no chain.

**M3 — Documents & thesis.** Drafts and chapters with versions (file + note
per version) and supervisor feedback (comments). Drafts are visible only to
scholar and supervisor. **Thesis submission** (chain): title, final file,
plagiarism tool + score and the plagiarism-check certificate (entered by
Library at its step), examiners (entered by Exam Office at its step).
**Submission gates** (Decided 2026-11-22; university settings, they block):
the scholar cannot submit before `min_duration_years` from admission (UGC
2022: 3; 0 = none; an unrecorded admission date blocks) nor with fewer than
`min_publications` approved publications that are accepted or published
(default 0 = off; optionally only those indexed in Scopus, Web of Science or
UGC-CARE) → 409 `thesis_gate`. The Library cannot approve a plagiarism score
above `max_plagiarism_percent` (UGC 2018 Level 0: 10%) → 422
`workflow_violation`; it sends the thesis back.
**After submission** (Decided 2026-10-24), on the approved thesis:
- **Examiner reports:** the Exam Office records each examiner's report —
  received date, recommendation (accept / minor revision / major revision /
  reject), report file.
- **Thesis reviewer portal** (Decided 2026-11-06): external
  reviewers are invited to a fully approved thesis and get a login. A reviewer
  sees only the thesis assigned to them, and only until their deadline. A
  submitted review joins the examiner reports above (UX_FLOWS.md Flow 8c).
  - **Invitation:** the Exam Office enters name, email, institution, deadline
    and whether download is allowed (default off), for any number of reviewers.
    It may extend a deadline, which reopens access.
  - **Reply:** the email carries the title, abstract and deadline and a secure
    link needing no login, to Accept or Decline. The thesis stays locked until
    they accept, which needs a no-conflict-of-interest tick and the
    confidentiality promise. A decline may give a reason. No reply in 7 days
    expires the invitation. The Exam Office is told of each outcome.
  - **Login:** accepting sends a single-use set-password link, never a password.
    Forgot-password covers recovery. The portal needs email configured.
  - **Deadline:** reminders 7 days and 1 day before, unless submitted. Access
    closes at the deadline (saved work kept, Exam Office told) and on submission.
  - **Review:** page comments are optional, on as few or as many pages as the
    reviewer likes, and they may upload their own review file instead. Submitting
    needs a recommendation (accept / minor revision / major revision / reject)
    and at least one comment or a file, then it locks.
  - **Release:** the scholar and supervisor see nothing until the Exam Office
    releases reviews, which it checks for names inside files first. The reviewer's
    name stays hidden on screen until the viva outcome is recorded.
  - **Copy protection:** every copy carries a random code, small and repeated on
    each page. The code holds no details; the server maps it to the reviewer, date
    and time, and only the Exam Office may look it up, with each lookup audited.
    The confidentiality promise says each copy is uniquely marked and traceable,
    not how. Download off: an in-app viewer with no download or print button.
    Download on: downloads logged, with short-lived links. Screenshots, photos and
    a determined technical reviewer cannot be fully stopped; the code is what
    traces a leak. Page images were rejected as too heavy, and on-PDF marking is
    left out for now.
- **Viva arrangement** (Decided 2026-11-19; Forms X and XI): once the reports
  are released, the Exam Office proposes the viva — date and time, venue and/or
  online link — and its board: the supervisor always sits on it, plus a
  chairperson (one), one or more external examiners (outside people, with an
  email) and members (faculty or outside). It is an approvable item (default
  chain: Vice Chancellor), with signing when the university requires it; the
  Exam Office edits it only while a draft or sent back. Submitting needs a
  date still to come, a venue or link, a chairperson and an external examiner.
  On approval the supervisor and the faculty on the board are notified (the
  scholar by the engine); the Exam Office then **emails the external
  examiners** the date, place and thesis title (may be sent again; 503 when
  email is not configured). One open arrangement per thesis at a time (409
  `viva_already_arranged`). The external examiners' names follow the examiner
  rule below until the viva is recorded.
- **Viva:** the Exam Office records date, venue or online link, panel and
  outcome (pass / re-defend after revision / fail) with the report file (Form
  XII), against the approved arrangement (409 `viva_not_approved` without
  one). A passed viva moves the scholar's stage to Viva. A viva is recorded
  after it happened and after the reports are released; pass and fail end the
  record, re-defend needs a new arrangement for the next.
- **Shodhganga deposit:** the Library records the deposit date, the
  Shodhganga handle/URL and the certificate file — a record, not a sync.
- **No-dues clearance** (Decided 2026-10-31; university setting
  `require_no_dues`, default off): a fifth item type, **no-dues**, initiated
  by the scholar, runs its own chain (default Supervisor (lab) → Department →
  Library → Research Office (fees)). While the setting is on, a thesis cannot
  be submitted without the scholar's approved no-dues → 409 `no_dues_pending`.
- **Thesis title** (Decided 2026-11-07): the title comes from the latest
  approved proposal entry in the register, never from the scholar. A thesis
  cannot start, and a certificate cannot be issued, until it is recorded
  (422 `title_not_approved`).
- **Provisional certificate** (Decided 2026-10-31): after a passed viva the
  Research Office issues the provisional PhD certificate (UGC 2022) — serial
  number `<university code>/PHD/<year>/<n>`, issue date, PDF with a QR code.
  The scholar's name and thesis title come from the portal; the degree name,
  wording and signatories are set per university at install (ARCHITECTURE §9).
  The QR opens a public verification page (`/verify/<random token>`, no login)
  showing only name, thesis title, unit, viva date, issue date and status
  (valid / revoked). The Research Office may revoke with a reason; nothing is
  deleted.
- **Examiner selection:** when the thesis chain has a Vice Chancellor step
  after the Exam Office, the Exam Office's entry is the proposed panel and the
  Vice Chancellor edits it down to the examiners selected before approving;
  the Exam Office can no longer change it once it has moved on.
- **Examiner confidentiality:** examiner names are visible only to the Exam
  Office, Research Office, Vice Chancellor and root admin until the viva outcome is recorded;
  the Exam Office releases reports (without names) to the scholar and
  supervisor.

**M4 — Coursework.** Course catalogue per unit (code, title, credits);
enrolments per scholar (semester, grade, grade points); coursework clearance
(chain) computes CGPA and records cleared date.

**M5 — Admissions** (internal record only — no public applicant portal).
Admin records each admitted candidate: entrance route (UGC-NET/JRF exempt,
GATE, university entrance test, other), score, interview date and outcome,
admission date. Converting an admission creates the scholar profile and login.

**M6 — Fellowships.** Per scholar: scheme (UGC-JRF/SRF, CSIR, INSPIRE,
institute, other), monthly amount, HRA, start/end, JRF→SRF upgrade date,
status.
- **Monthly claim** (built 2026-11-15): the scholar claims one month of their
  own active fellowship — the month, days of leave taken, an optional note —
  and it goes up the fellowship-claim chain (F3). One claim per fellowship
  per month; only a month inside the fellowship that has already begun. The
  claim carries the amount the fellowship pays for the month (fellowship +
  HRA) as it stands when submitted; leave days are recorded for the
  approvers and do not change the amount. An approved claim is a record of
  who certified the month: it pays nothing and writes nothing to the ledger
  (§7) — the office records the payment in the ledger as before.

**M7 — Research projects.** Funded projects: PI (faculty), agency
(DST/SERB/ICSSR/…), title, sanction number, amount sanctioned, duration,
members (scholars and their role).

**M8 — Grant ledger.** Disbursements and expenses against a project or
fellowship (head: salary/fellowship, equipment, consumables, travel,
contingency, overhead), and utilisation certificates per period (file +
submitted date).
- **Generated UC** (Decided 2026-10-31): for a project's UC period the system
  drafts the certificate as a PDF in the GFR 12-A layout — sanctioned amount,
  received to date, spent per head in the period and cumulatively, unspent
  balance. The PI signs it outside; the signed scan is attached as today.
- **Grant alerts** (daily job): the PI and the Research Office are told when a
  project ends within 60 days, and when an expense takes its unspent balance
  below 10% of the amount received (told once, at the crossing), or when the
  first expense goes out with no money recorded as received.
- **Entries that look wrong** (Decided 2026-11-06, warn and confirm, never
  block): an expense beyond the balance, spending beyond the sanctioned amount,
  a future date, or a date outside the project or fellowship period. The
  person confirms what they saw, the entry keeps the warnings it was confirmed
  with, and the department's admin is told who entered what.

**M9 — NAAC research data** (Decided 2026-10-31). For a range of academic
years, the Research Office and root admin export the research data NAAC
Criterion 3 asks for, one sheet each: funded projects and grants received per
year; PhD scholars registered and awarded per guide per year; publications per
year with indexing (UGC-CARE / Scopus / WoS); books and chapters. Built from
the records already kept — no extra data entry. Publications are the scholars'
(approved) and the faculty's (verified by the Library, M1); a paper both
recorded under one DOI is one row naming each of them ("Recorded by"). Metric numbering follows the
framework in force; the sheets carry the underlying rows, not computed scores.

## 7. Non-Goals

Intentionally NOT in this version:
- A public applicant portal (admissions is internal record only).
- NIRF/AISHE accreditation packs (NAAC Criterion 3 research data is M9),
  Shodhganga sync (the deposit is recorded by hand, M3).
- PFMS integration and agency-specific UC formats (the generated UC follows
  GFR 12-A, M8).
- Plagiarism-check API integration (scores are entered by the Library).
- Payroll/accounting integration (the ledger records, it does not pay).
- Fees: a university's own fee system keeps scholars' fees; Anveshan keeps no
  fee records or payment status. A fee notice goes on the notice board (F18)
  (Decided 2026-11-22, owner).
- Multiple universities in one installation (one installation per
  university).
- Google Calendar integration; GitHub mirroring; two-way WhatsApp (replies,
  chat bots) — WhatsApp is outbound notifications only (F5).
- Committee-member logins (RAC outsiders) — they get PDFs and email. Thesis
  reviewers are the one exception (M3).
- Per-unit approval chains (chains are university-wide).

## 8. Build Phases

1. **Foundation:** org tree, users + multi-role assignments + scope, auth,
   modules switch, approval-chain engine and settings, audit, files,
   notifications plumbing, clay UI kit + owl.
2. **Core daily use:** directory, meetings with sharing, APR with chain, RDC
   register, progress seminars (scheduling, grading, AI to-dos), dashboards,
   timeline, search, comments, APR PDF + register export.
3. **Research record & onboarding:** bulk import (F16), university-email
   login and set-password email (F2), publications (chain), conferences,
   documents & thesis submission (chain) through examiner reports, viva and
   Shodhganga deposit (M3).
4. **Academic administration & UGC rules:** coursework + clearance (chain),
   admissions; UGC rules warned before they are broken (6-year maximum with
   allowed extensions and leave, minimum coursework credits — supervisor caps
   are already enforced, F6); leadership view (scholars at risk, time to
   completion and drop-outs by unit).
5. **Grants:** fellowships, research projects, grant ledger.
6. **Production packaging:** self-hosted Docker Compose stack for a
   university server/NAS (ARCHITECTURE.md §4).
7. **Reach & research administration** (Decided 2026-10-31): WhatsApp
   notifications (F5); generated utilisation certificates and grant alerts
   (M8); no-dues clearance before thesis submission (M3); provisional PhD
   certificate with QR verification (M3); NAAC Criterion 3 research data
   (M9).
8. **Mobile apps:** a Flutter app (Android + iOS) in `mobile/`, on the same
   `/api/v1`, themed from DESIGN_SYSTEM.md, reaching parity with the web
   screen by screen; push notifications after parity of the inbox.

Each phase ends with a check-in with the owner before the next starts.

## 9. Success Metrics

**Primary (pilot):**
- One department, ≥10 scholars, ≥2 supervisors using it weekly for one full
  semester; the HoD opens the dashboard at least fortnightly.
- ≥80% of the period's APRs submitted and fully approved inside the system.

**Secondary:**
- RDC register export in < 5 minutes.
- Zero "where is my approval" queries to the research office from pilot
  scholars — every item shows which step it is at.

## 10. Constraints

- **Technical:** FastAPI + Node export + Next.js on Postgres with
  S3-compatible files (ARCHITECTURE.md). Development/testing on free cloud
  tiers (Neon, Render, Vercel, Cloudflare R2); production self-hosted per
  university on a home server/NAS via Docker Compose. Repo develops on an
  exFAT volume (AppleDouble junk — gitignored).
- **Business:** solo developer, no funding; department-first pricing
  (₹50k/yr entry).
- **Design:** warm academic claymorphism (DESIGN_SYSTEM.md) — enjoyable
  enough that weekly use pulls itself.
- **Timeline:** pilot-ready within months; phases ship in order (§8).

## 11. Assumptions

- UGC 2022 PhD Regulations remain operative.
- Committee names (RDC/DPGC/DRC/RAC) vary by university, but the "decision +
  resolution number" pattern is universal.
- All users have email addresses usable for login and notifications.
- The university provides an SMTP account in production.
- Manual plagiarism-score entry by the Library is acceptable.

## 12. Open Questions

- Pricing: per scholar vs flat per department? (Test with first pilot.)
- Which university is the pilot? No commitment yet.
- Do PDFs need per-university templates, or one generic UGC format?
- ~~Co-supervisors?~~ Resolved 2026-10-21: per-university setting
  off / view / approve (F6).
- Does co-supervision count toward the co-supervisor's UGC cap? (Default:
  no — confirm with the pilot university's ordinance.)
- May a supervisor grade their own scholar at the seminar? (Default: yes, as
  any panel member — confirm with the pilot university.)
- Bulk import: legacy scholars may already exceed today's UGC caps
  (admitted under older rules). Default: the cap holds and the row fails —
  confirm with the pilot whether imports may override with a recorded reason.
- Examiner confidentiality (M3): confirm the pilot university's ordinance —
  may the supervisor see examiner names before the viva?
- With single sign-on configured, should password login be switchable off?
  (Default: both stay on.)
- NIRF / AISHE reporting pack: a non-goal today; revisit after the pilot with
  real data in hand.
- ~~Signing inside the portal (F17b): what proves the signer is present?~~
  Resolved 2026-11-18: a fresh authenticator code at each signature, then the
  admin-confirmed specimen signature is stamped.
- ~~A signer without a smartphone?~~ Resolved 2026-11-18: an emailed code
  is accepted for now (F17b); a code by text message comes later if a
  university needs it. Accepted risk: email may be open on the same computer.
- ~~A legally recognised e-signature?~~ Resolved 2026-11-18: Aadhaar eSign
  later, not in the first build.
- Will the pilot university accept the PhD file (F17) with electronic approval
  records and signed scans, or does it still need every page signed on paper?
- ~~Grant ledger: may a PI enter expenses on their own project?~~ Resolved
  2026-10-21: yes, on their own projects only (SECURITY.md §3).

## 13. Definition of Done

- [ ] Each phase's features meet their acceptance criteria
- [ ] Every approval chain verified by click-through with every role
      involved, including send-back to an earlier step
- [ ] Scope negatives pass: out-of-unit heads, other scholars, offices outside
      their item types all get 403
- [ ] Tests pass (`pytest` / `node:test` / `npm run build` — CI green)
- [ ] Fresh install works (`alembic upgrade head` + seed) on cloud and on the
      self-hosted compose stack
- [ ] SECURITY.md checklist satisfied; docs match behaviour
