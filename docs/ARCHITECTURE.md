# Architecture

## 1. System Overview

PhD Tracker is a [Frappe framework](https://frappeframework.com) app: a monolithic,
metadata-driven application where forms, roles, permissions, workflows, and audit
trails are configuration (DocType JSON) plus thin Python controllers. It rides on
MariaDB, Redis (cache/queue), and Python. Each university deployment gets its own
bench site and database.

## 2. Architecture Pattern

- **Pattern:** Monolith (Frappe low-code app; DocTypes are the schema, workflow
  engine drives state, print formats produce paper).
- **Reason:** The entire v1 is CRUD + one approval chain + PDFs. A workflow engine,
  RBAC, and print generation already exist in the platform — building them again
  (as the abandoned Spring Boot prototype did) is the exact cost this choice avoids.

## 3. Technology Stack

| Concern | Choice |
|---|---|
| Backend | Frappe framework v15 (Python 3.10–3.13; dev uses pyenv 3.12 — system 3.14 unsupported) |
| Frontend | Stock Frappe Desk (v1); no custom UI |
| Database | MariaDB 10.6+ (via bench) |
| Cache/Queue | Redis |
| Authentication | Frappe's built-in email/password + session; roles server-side |
| Storage | Frappe file attachments (site-local) |
| Hosting | Per-university bench instance (universities demand their own server/data residency) |
| Email | Frappe email framework (site SMTP config) |
| PDF | Frappe print formats (wkhtmltopdf) |

## 4. System Components

### DocTypes (schema + forms)
- PhD Scholar, PhD Supervisor, Meeting Record, Progress Report, PhD Milestone
- Defined in JSON (`phd_tracker/phd_tracker/doctype/*/*.json`), synced to DB on
  `bench migrate`.

### Workflow engine
- "Progress Report Approval" (Draft → Submitted → Approved/Rejected) defined
  programmatically in `install.py` (states, transitions, `allow_edit` per role).
  Server-side enforced.

### Install hook
- `install.py after_install()`: creates the three roles (PhD Scholar, PhD Supervisor,
  Research Office Admin), the workflow, and registers our DocTypes in Global Search
  Settings (so Desk search covers them).

### Print formats and reports
- Compliance artifacts (APR PDF, milestone register). v1 ships them as fixtures
  synced by `bench migrate` via `hooks.py`:
  - `fixtures/print_format.json` — "APR" custom HTML print format (`custom_format: 1`)
    on Progress Report (scholar, supervisor, dates, summary).
  - `fixtures/report.json` — "Milestone Register" query report (SQL join onto
    PhD Scholar) with Scholar / Department filters; exportable to PDF/Excel.

## 5. Architecture Diagram

```
Browser (Frappe Desk, stock UI)
        │  HTTPS
        ▼
Bench / Frappe app  ──  Workflow engine (server-side state transitions)
   ├── DocType controllers (phd_tracker)        │
   ├── REST API (auto-generated per DocType)    │
   └── Print formats (PDF)                      │
        │                                       │
        ▼                                       ▼
   MariaDB  ◄────────────────────────────  Redis (cache/queue)
```

## 6. Data Flow — APR approval (the critical chain)

1. Scholar logs in, creates Progress Report (period, summary).
2. Desk validates field constraints (required, options).
3. Scholar clicks **Submit Report** → workflow transition Draft→Submitted
   (role `PhD Scholar` only; enforced server-side).
4. Supervisor opens the report list, reads summary, writes comment.
5. Supervisor clicks **Approve** (doc_status 0→1, submit) or **Send Back**
   (→ Rejected, back to scholar for revision).
6. `on_submit` sets `approved_on` automatically.
7. Every change is versioned (`track_changes: 1`) — the audit trail.

## 7. Project Structure

```
phd-tracker/
├── AGENTS.md               ← agent instructions (root: where tools discover them)
├── docs/                   ← source of truth for this product
│   ├── PRD.md  DESIGN_SYSTEM.md  ARCHITECTURE.md  DATABASE.md
│   ├── SECURITY.md  CODE_STYLE.md  TESTING.md  UX_FLOWS.md
├── pyproject.toml          ← flit build (bench installable)
└── phd_tracker/            ← the Frappe app
    ├── hooks.py  install.py  modules.txt  patches.txt
    └── phd_tracker/doctype/
        ├── phd_scholar/  phd_supervisor/
        ├── meeting_record/  progress_report/  phd_milestone/
```

## 8. Dependency Rules

- Business logic lives in DocType controllers (`validate`, `on_submit`) only where
  platform config can't express it. Prefer workflow/permission config over code.
- No client scripts (`.js`) in v1 — stock Desk behavior only.
- The app depends on `frappe` only. No third-party Python dependencies.
- Custom UI, when it comes, is a Frappe web portal/page — never a parallel frontend
  service.

## 9. Key Technical Decisions

| Decision | Context | Alternatives | Reason |
|---|---|---|---|
| Frappe framework | Needed auth, RBAC, workflow, PDF, audit in one | From-scratch (Spring Boot/Django); Unity's commercial module | Platform is GPLv3/free; incumbents (Unity) prove the play; prototype proved from-scratch costs months |
| Stock Desk UI | v1 is internal-tool-shaped | Custom React portal | Zero UI investment before pilot validation |
| Workflow in install.py, not fixtures | Workflow must exist on every fresh install | JSON fixtures import | Programmatic insert is explicit and debuggable; fixtures import order is fragile |
| Per-university instances | Indian universities demand own server/data residency | Shared multi-tenant cloud | Sales reality; Frappe multi-tenancy via sites exists but procurement wants ownership |
| Fixed milestone types | UGC 2022 lifecycle is nationally standardized | Configurable workflow engine per university | v1 simplicity; configurability waits for paying demand |
| Legacy Spring Boot prototype removed | Superseded by Frappe decision | Keep as parallel backend | Two backends = drift; domain ideas (research_title, doc versioning, notification channels) noted in DATABASE.md for later |

## 10. Performance Considerations

- Frappe indexes DocType link fields and `modified` by default — our access patterns
  (list by scholar, list by status) are covered in v1 scale (a department ≈ tens of
  scholars; a university ≈ hundreds).
- No external API calls in any request path in v1.

### Performance playbook (triaged against this stack)

| Item | Verdict | Home |
|---|---|---|
| Compress API responses in transit | **Applies at deployment.** Enable gzip/brotli on the nginx edge in front of bench for JSON/text responses >1 KB (Desk + REST); Accept-Encoding negotiation is browser-automatic. Do not compress print-format PDFs — already compressed by wkhtmltopdf. Verify: transfer sizes drop, JSON still parses on the client. | Pilot deployment checklist (TESTING.md flow) |
| Batch inserts/updates | **Rule for all future code.** No per-row INSERT/UPDATE loops; bulk writes, chunked ≤1000 rows, inside one transaction. First consumer: seed fixtures. | CODE_STYLE.md §10 |
| Circuit breaker for slow dependencies | **Deferred — nothing to break yet.** v1 has zero external calls in request paths. When plagiarism/GitHub APIs arrive they run as Frappe background jobs with timeouts and fail-soft fallbacks (manual score entry), never inline middleware; a degraded dependency must not drag unrelated flows. | §12 Failure Scenarios |
| Optimistic UI updates | **Deferred to custom UI.** v1 is stock Desk with no client JS of ours. Principle recorded for the future portal. | DESIGN_SYSTEM.md §1 |
| Cache rendered pages/fragments | **Not applicable in v1 — would be a correctness bug.** Desk views are per-user/personalized; print-format PDFs are compliance artifacts that must reflect current data on every render. Revisit only if a public page or heavy aggregate report appears. | — |

## 11. Scalability Considerations

- One department → one university: add per-department `department` filtering
  (field already on Scholar/Supervisor).
- Multiple universities: separate sites/instances; shared app code updates via
  `bench update`.

## 12. Failure Scenarios

- **Database unavailable:** Frappe returns 502/500; no data loss (transactions are
  atomic; Redis queue retries).
- **Email/SMTP not configured:** APR submit still works; notification silently logs.
  Compliance chain never depends on email.
- **Workflow missing after botched upgrade:** `install.py` is idempotent
  (`db.exists` guards) — re-running migrate restores roles/workflow.
- **External dependency slow or down (post-v1: plagiarism API, GitHub mirror):**
  such calls run as background jobs with timeouts and fail-soft behavior (score
  recorded manually; mirror lags, nothing blocks). A degraded external service must
  never block a request path or a committee export. Circuit-breaker-style
  fast-failing comes with the first real dependency, not before.
- **App updated with breaking DocType change:** Frappe patches (`patches.txt`) are
  the only sanctioned migration path — never hand-edit synced JSON in the DB.