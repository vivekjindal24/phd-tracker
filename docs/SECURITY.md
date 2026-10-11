# Security Guidelines

## 1. Authentication

- **Authentication Provider:** Frappe's built-in system (email + password,
  server-side sessions, CSRF-protected).
- **Methods:** Email/password only in v1. OAuth/social login: not needed for a
  university-internal tool; defer until a pilot asks.

## 2. Authorization

Roles (created on install): **PhD Scholar**, **PhD Supervisor**, **Research Office
Admin**.

Permissions (defined in DocType JSON; enforced server-side by Frappe):

| DocType | PhD Scholar | PhD Supervisor | Research Office Admin |
|---|---|---|---|
| PhD Scholar | read | read | full |
| PhD Supervisor | read | read | full |
| Meeting Record | create, read, write | create, read, write | full |
| Progress Report | create, read, write | read, write, **submit** | full + submit |
| PhD Milestone | read | read, write | full |

- Workflow actions are additionally role-gated: only Scholars can submit reports;
  only Supervisors can approve/reject (workflow `allowed` per transition).
- **Authorization must be enforced server-side** — and in Frappe it is: the same
  rules apply to Desk, REST API, and print. Never loosen a role to "make it work."
- Known v1 gap (deliberate): a Scholar can currently read other scholars' meeting
  records/reports. Ownership-based row filtering (per-scholar visibility) is a
  roadmap item — acceptable for a single-department pilot where the supervisor
  cohort is small, must be fixed before multi-department sale. See PRD Future.

## 3. Secrets

- Never hard-code credentials; never commit production secrets.
- Site-level secrets (DB password, SMTP, API keys) live in the instance's
  `site_config.json` / `common_site_config.json` — never in this repo.
- Never expose private secrets to any client code.
- Rotate compromised credentials immediately.

## 4. Environment Variables

- **Public:** none (no client-side config keys).
- **Private (per-instance, never in repo):** `db_name`, `db_password`, SMTP creds,
  encryption key — all managed by bench site config.

## 5. API Security

Frappe's auto-generated REST API covers every DocType and inherits the same
permission matrix:
- **Input validation:** server-side field validation (reqd, options, Link
  integrity) on every write path, Desk or API.
- **Rate limiting:** Frappe defaults; tighten if exposed beyond campus network.
- **CORS:** default-closed; enable only for a named portal origin if custom UI is
  ever built.
- **Authentication:** session or Frappe API token — permissions identical either way.
- **Authorization:** per the matrix above; ownership checks (e.g. "this scholar can
  only touch their own reports") come with the row-filtering roadmap item.

## 6. Data Protection

- **Sensitive data:** scholar/supervisor emails, meeting minutes, research
  summaries, GitHub URLs.
- **Encryption:** transport via HTTPS (instance must front bench with TLS);
  at-rest is the university's DB responsibility.
- **Retention:** records are permanent by design — they ARE the PhD's audit trail.
  Soft-delete (trash) only; no hard deletes by anyone except System Managers.
- **Deletion requests:** escalate to the project owner — never auto-delete
  compliance records.

## 7. Logging

- **Never log:** passwords, session tokens, full personal details.
- **Log (Frappe error/activity logs):** authentication events, document mutations
  (version history), workflow transitions, errors with context.
- Instance operator owns log retention.

## 8. File Uploads

- **Allowed file types (v1):** `.pdf`, `.docx`, `.tex`, `.zip` — thesis/draft
  artifacts only.
- **Maximum size:** 25 MB per file.
- **Validation:** extension allowlist + size; content-type sniffing when custom
  upload screens arrive (stock Frappe attachments in v1).
- **Storage:** site-local `public/files` / private files — never a third-party
  bucket without a university's explicit sign-off.

## 9. Security Checklist

- [x] Roles and permission matrix defined in DocType JSON (server-side)
- [x] Workflow actions role-gated
- [x] No secrets in repo; site config holds credentials
- [x] Soft-delete-only data retention policy
- [ ] Ownership row-filtering for scholars (before multi-department)
- [ ] HTTPS verified on pilot deployment
- [ ] File upload allowlist enforced (when custom uploads arrive)
- [ ] Dependencies reviewed (`pip-audit` on the bench env) before pilot
- [ ] Backup schedule verified (bench site backup cron)