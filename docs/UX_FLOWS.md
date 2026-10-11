# UX Flows

The daily-use journeys. Each is the manual E2E checklist until automated tests
replace it.

## Flow 1 — Scholar submits six-monthly progress report

1. Scholar logs into Desk (role: PhD Scholar).
2. Opens Progress Report list → New.
3. Fills scholar (link), report_year, period, summary of work.
4. Saves — doc is Draft, editable by scholar.
5. Clicks **Submit Report**.
6. Doc moves to Submitted; supervisor sees it in their list.

**Success:** State Submitted; summary no longer editable by scholar
(workflow `allow_edit` = PhD Supervisor).
**Failure paths:**
- Wrong role tries to submit → transition not offered; API attempt rejected
  server-side.
- Missing required field → Frappe validation error naming the field.

## Flow 2 — Supervisor approves or sends back

1. Supervisor logs in, filters Progress Report list by state Submitted.
2. Opens a report, reads summary, writes supervisor_comment.
3. Either **Approve** (→ Approved; doc_status 1; `approved_on` set) or
   **Send Back** (→ Rejected with the comment as the reason).
4. If sent back: scholar opens the Rejected report, revises summary, clicks
   **Revise and Resubmit** (→ Draft), then **Submit Report** again.

**Loading:** stock Desk save spinner; no custom states.
**Error:** transition failure surfaces Frappe's message; version history shows
every cycle (draft → submitted → rejected → draft → …) — this full trail is the
audit artifact.

## Flow 3 — Supervisor logs a meeting

1. Supervisor opens Meeting Record → New.
2. Selects scholar, fills meeting_date, agenda, minutes, action items,
   next_meeting_date.
3. Saves.

**Success:** Record visible to scholar and research office; versioned.
**Empty state:** list empty for a new scholar — expected; the first meeting is
created manually (no scheduling/calendar integration in v1).

## Flow 4 — Research office records an RDC milestone

1. Admin opens PhD Milestone → New.
2. Selects scholar, milestone type (e.g. Proposal Approval (RDC)), status
   Approved, fills approval body, resolution number, resolution date.
3. Saves; exports the register via print format for the committee meeting.

**Success:** Milestone read-only to the scholar, listed on their record.
**Error:** milestone_type not in the Select list → rejected on save.

## Flow 5 — Buyer / committee (no login)

1. Registrar requests the half-yearly compliance pack.
2. Research office admin exports per-scholar PDFs (APR + milestone register).
3. PDFs are emailed; no committee member ever opens the system.

**Success:** pack produced in minutes, with the audit trail behind every page.
**Empty state:** a scholar with no records yet exports as a cover page with
"no records" — never a blank page.