# UX Flows

> v3 rewrite (2026-10): flows for every level of the university. The API is
> the enforcer on every step; the UI only offers what the user's roles,
> scope, the item's state and the enabled modules permit. Each flow is the
> manual E2E checklist (TESTING.md) until it is automated.

## Flow 0 — Login, session, multi-role home

1. `/` → the public landing page (what Anveshan is, with **Log in** → `/login`);
   a visitor with a valid session goes straight to `/home`. The wordmark on
   `/login` links back to `/`.
2. Email + password → `POST /api/v1/auth/login` → access token in memory,
   refresh token in localStorage. When configured, **Continue with Google /
   Microsoft** → provider → back to `/login` with a one-time code exchanged
   for the same token pair. **Forgot password?** emails a set-password link
   (same message whether or not the email exists). `/auth/me` returns role assignments and
   enabled modules.
3. Navigation shows the union of the user's roles, grouped: **My work**
   (queue, scholars/meetings/reports), **My unit** (heads/admins),
   **Office** (offices), **Settings** (root admin). Disabled modules never
   appear.
4. `/home` stacks one dashboard section per role (e.g. Dr. Meera: "Your
   queue" → "Your scholars" → "Computer Science overview" → "Department
   admin"). A role switcher is not needed — everything is on one page.
5. Idle past 30 min → next call 401s → one silent refresh-and-replay; a
   second 401 → `/login` with a message.
6. Cold start: if the API takes > 3 s, the sleeping owl shows "Waking up the
   server…" until it answers.

**Failure:** bad credentials → error envelope inline; 5 failures → 429
"Too many attempts, try again in 15 minutes". SSO with an email that has no
active account → "No Anveshan account for this email — ask your department
admin".

## Flow 1 — Scholar submits a progress report (APR chain)

1. Scholar → **Reports** → **New report**: period + year + summary.
2. Save → **Draft**; **Submit for approval** → badge **In review ·
   Supervisor**. The item page shows the chain as a row of clay steps with
   the current one highlighted.
3. Each approver sees it in **Your queue**; the scholar sees the step move
   (**In review · Department**, **In review · Research Office**).
4. Final approval → **Approved** badge pops, the owl cheers once, confetti
   (reduced-motion: none). The report is locked for everyone.

**Failure paths:** duplicate period → 409 `duplicate_apr` inline; a
non-initiator never sees the New button and the API 403s anyway.

## Flow 2 — Approver acts on any chain step

1. Approver opens **Your queue** (items at a step they can act on, oldest
   first, with item type, scholar and days waiting).
2. Opens an item: content, files, comments, full approval history.
3. **Approve** (optional comment) → next step, or Approved if last.
4. **Send back** → picker: "To the scholar" or any earlier step by name
   (e.g. "Supervisor"); comment required. The receiver is notified and sees
   the reason pinned at the top.
5. Scholar edits a **Sent back** item → **Resubmit** → the chain restarts
   from step 1 with the snapshot taken at the original submit.

**Rules surfaced in the UI (enforced in the API):** if the user already acted
on the previous step, the buttons are replaced by "Another approver needs to
act on this step"; step-only fields (Library's plagiarism score, Exam
Office's examiners) appear only to that step's actor.

## Flow 3 — Log a meeting and choose who above can read it

1. Supervisor (or scholar) → **Meetings** → **Log meeting**: scholar,
   date, agenda, minutes, action items, next date.
2. **Share minutes with** (supervisor only): checkboxes Unit heads /
   Research Office / Admins — all unticked by default, with the hint
   "Unticked roles see only that the meeting happened."
3. Save → full record visible to scholar and supervisor; a HoD in scope sees
   "Meeting held · 21 Oct 2026" unless Unit heads was ticked.

**Error:** scholar with no supervisor → form refuses ("a meeting needs both
parties"). Backdated dates allowed, visibly timestamped; dates more than a
day in the future are refused (meetings are logged after they happen). A
co-supervisor (setting on) may log their own meetings but never sets sharing.

## Flow 4 — Head of Department / Dean oversight

1. HoD opens `/home` → **Computer Science overview**: scholars by stage
   (clay bar), overdue APRs (names), items stuck > 14 days (step + days),
   supervisor load vs UGC cap (bars turn coral at cap), publications this
   year.
2. Clicking any number opens the filtered list; clicking a scholar opens the
   timeline (meeting minutes redacted unless shared).
3. A Dean sees the same per department, side by side, plus faculty totals.
4. **Unit summary PDF** downloads the overview for the committee meeting.

## Flow 4b — Leadership view and UGC time limit (PRD Phase 4)

1. Head / admin / Research Office → **Leadership** (or *Leadership view →*
   on a unit's home section): current scholars, completions with median
   years to complete, drop-outs and rate, supervisors at the UGC cap — for
   the unit and per child unit (click to drill down).
2. **Scholars at risk**: overdue progress report, nearing (180 days) or past
   the maximum duration, no supervision meeting in 120 days, extensions or
   leave beyond their limits — each with its reason.
3. On a profile, **Time limit** shows the must-submit-by date (admission +
   6 years + extensions + relaxation); an admin or the Research Office
   records extensions / leave with the resolution number; the scholar's home
   warns when the limit is near or past.
4. **Mark as left** (withdrew / registration cancelled) on the profile frees
   the supervisor's slot and counts as a drop-out; *Undo* re-checks the cap.

## Flow 5 — Admin manages people (scoped)

1. Department admin → **My unit → People**: scholars and faculty of their
   subtree.
2. **Add scholar**: name, email, roll number, unit (subtree only), research
   title, admission date, supervisor (only faculty with spare cap are
   listed; over cap → 409 shown inline), and a co-supervisor (any faculty,
   shown only when co-supervision is on). The user gets a set-password
   email (or, unticked, the admin sets an initial password); **Email a
   set-password link** on the profile re-sends it.
3. **Add faculty**: designation sets the default cap.
3b. **Import** (PRD F16): download the template → fill in Excel → upload →
   dry-run table (rows to create, rows already present, row errors with row
   and column) → fix and re-upload until clean → **Import** (all or nothing),
   optionally **send invitations**.
4. **Roles**: assign HoD / admin for units in their subtree only.
5. Root admin additionally sees **Settings**: org tree editor (add / rename
   / move units), **Approval chains** (per item type: ordered clay step chips,
   add / remove / reorder, saved with a note "applies to new submissions
   only"), **Modules** (switches), **Co-supervision** (Off / View /
   View + approve).

## Flow 6 — Research office keeps the RDC register

1. **Register → Add decision**: scholar, milestone type, status, body
   (RDC/DPGC/DRC/RAC), resolution number/date, notes.
2. **Register PDF / CSV** for the committee meeting.
3. The scholar's RDC status updates on their profile and on head dashboards.

## Flow 6b — Progress seminar (PRD F15)

1. HoD / department admin → **Seminars → Schedule**: title, date & time,
   venue/link, report due date, period, pick scholars (their unit) and panel.
   Everyone concerned is notified.
2. Scholars see the seminar and their report deadline on Home; the report
   page shows "Due 30 Nov" / "Overdue".
3. If the university requires a hardcopy, the department ticks "hardcopy
   received" per scholar.
4. On the day, each panel member (and attending faculty, if allowed) opens
   the seminar → per scholar: rubric scores + comment → **Submit grades**.
5. Supervisor → **Review**: sees all grades; **Suggest points with AI** fills
   a draft list (part + point); edits, accepts, adds → **Finalise**.
6. Scholar is notified, sees all marks and comments, and the points appear in
   **My to-dos**, grouped by part; ticks them off as done.

## Flow 7 — Publication verified by the Library (module)

1. Scholar → **Publications → Add**: details, indexing, DOI, PDF →
   **Submit**.
2. Supervisor confirms authorship → Library sees it in **Your queue**, checks
   the journal against Scopus / WoS / UGC-CARE and approves, or sends back
   (e.g. to the scholar: "Journal not in UGC-CARE list") → Research Office
   approves.

## Flow 8 — Thesis submission (module)

Scholar uploads the final thesis → Supervisor → Department → **Library**
enters plagiarism tool + score and approves → **Exam Office** records receipt
and examiners → Research Office final approval → scholar stage moves to
Thesis Submitted.
After approval, on the thesis page: Exam Office adds each **examiner report**
→ **Release reports** (scholar and supervisor see them, without examiner
names) → records the **viva** (outcome Pass → stage Viva) → Library records
the **Shodhganga deposit** (date, handle, certificate).

## Flow 9 — Coursework (module)

1. Exam Office → **Coursework**: picks a scholar, enrols courses from the
   unit catalogue, enters grades. The card shows credits and CGPA against
   the university minimums (Settings → UGC rules) and lists what still
   blocks clearance.
2. **Start coursework clearance** (offered once nothing blocks it) →
   **Submit** (the API recomputes credits + CGPA and refuses a record below
   the minimums) → Department confirms → Exam Office marks **Cleared** →
   Research Office notes it; the cleared date shows on the profile and the
   scholar's home. The stage itself is moved by the admin / register, as
   before.

## Flow 10 — Admission to scholar (module)

Admin (their units) or Research Office (any) → **Admissions → Record a
candidate**: entrance route and score, interview date, admission date; set
the result in the list. For a **Selected** candidate, type the roll number →
**Make scholar**: the scholar profile and login are created (same rules as
Flow 5), the candidate gets a set-password email, and the row links to the
new profile. Heads of the unit see the list read-only.

## Flow 11 — Grants (modules)

- **Fellowships** (`/fellowships`): admin / research office records scheme,
  amounts, dates; **Record SRF upgrade** sets the date, scheme and new amount;
  scholars see their own (and the end date on Home), supervisors their
  scholars'; the daily job reminds the scholar and supervisor 60 days
  before the end.
- **Projects** (`/projects`, `/projects/<id>`): PI, agency, sanction, members
  (scholars from any unit); the PI and members see the project, heads their
  subtree.
- **Ledger** (on the project page; on a fellowship for offices and heads):
  disbursements and expenses with a running balance and received / spent /
  balance against the sanction; the PI may add expenses on own projects;
  utilisation certificates per period, with the signed file attached and the
  submitted date recorded.

## Flow 12 — Notifications

Bell icon with unread count → inbox (newest first, mark read). Each item
links to the record. Below the inbox, **Email me when…**: email on/off per
category, saved on each tick; in-app always on. (On the inbox page, not
Settings: Settings is the root admin's.)

## Flow 13 — Search

Search box in the top bar; partial matches (`PHD-CS-2024-`); results grouped
by entity, scoped exactly like the lists, only enabled modules, meeting
minutes never matched unless shared with the viewer.

## Flow 14 — Committee / external (no login)

Admin or head downloads PDFs (APR, scholar record, register, unit summary)
and emails them. Empty states export as a cover page with "No records" —
never a blank PDF.
