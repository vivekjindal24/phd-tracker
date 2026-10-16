# UX Flows

> v2 rewrite: Frappe Desk mechanics are superseded by the Next.js web app
> (`web/`). The API is the enforcer on every step; the UI only offers what the
> current role/state permits. Each flow is the manual E2E checklist
> (docs/TESTING.md) until it's automated.

## Flow 0 — Login / session

1. User opens `/` → redirected to `/login` (no token) or `/dashboard` (valid).
2. Enters email + password → `POST /api/v1/auth/login` → access token in memory
   (module variable), refresh token in localStorage.
3. Nav renders only the role's routes (a scholar never sees Supervisors;
   supervisors get no "New report" button — the API would 403 either way).
4. Idle past 30 min → next call 401s → one silent refresh-and-replay; a second
   401 → back to `/login` with a message.

**Failure:** bad credentials → the API's error envelope shown inline, no
silently empty dashboard.

## Flow 1 — Scholar submits six-monthly progress report

1. Scholar logs in (role: scholar), opens **Reports**.
2. Clicks **New report** (only scholar/admin see it), picks period + year,
   writes the summary. Their own scholar record is attached automatically.
3. Save → card appears as **Draft** with an Edit control on the detail page.
4. Opens it → edits summary → **Submit for approval**.
5. Detail shows the **Submitted** badge; the summary editor is gone (locked).

**Failure paths:** duplicate (scholar, year, period) → 409 `duplicate_apr`
shown inline; supervisor attempting the same create → the button isn't
rendered, and the API returns 403 regardless.

## Flow 2 — Supervisor approves or sends back

1. Supervisor opens **Reports**, filters by state = Submitted.
2. Opens a report, reads the summary, writes a supervisor comment, then either
   **Approve** (→ Approved, `approved_on` set) or **Send back** (→ Rejected
   with the comment as the reason).
3. If sent back: the scholar opens the Rejected report, edits the summary,
   **Resubmit** (→ Draft), then **Submit for approval** again.

**Immutability:** once Approved, no role sees any control — the compliance
record is frozen server-side (workflow.py) and the UI mirrors it. The
`audit_log` carries the full cycle (draft → submitted → rejected → draft → …).

## Flow 3 — Log a meeting

1. Supervisor (or scholar, or admin) opens **Meetings** → **Log meeting**.
2. The counterparty is picked from the caller's own scoped scholar list;
   meeting_date, agenda, minutes, action items, next meeting date are filled.
3. Save → the row is visible to both parties and the research office.

**Error:** a scholar with no supervisor assigned → the form refuses with a
message (a meeting needs both parties); backdated dates are allowed (real
life) but visibly timestamped.

## Flow 4 — Research office records an RDC milestone

1. Admin opens **Milestones** → **Add milestone**, picks the scholar, the UGC
   lifecycle type, status, approval body, resolution number/date, notes.
2. **Register PDF / Register CSV** download the milestone register for the
   committee meeting (export service, admin-only; the token is forwarded).

**Success:** scholars see their milestones read-only; supervisors/admin can
create/update.

## Flow 5 — Buyer / committee (no login)

1. Registrar requests the half-yearly compliance pack.
2. Admin opens the approved APR → **Download PDF** (export service renders it
   from the API's `/internal` response).
3. PDFs are emailed; no committee member ever opens the system.

**Empty state:** a scholar with no records exports as a cover page with
"no records" — never a blank PDF (tested in the export suite).

## Flow 6 — Search

1. Any role types in **Search** (trigram, partial matches like
   `PHD-CS-2024-` work).
2. Results group by entity; rows are scoped exactly like the lists — a
   scholar's search never surfaces another scholar's records.