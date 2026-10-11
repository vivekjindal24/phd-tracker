# Code Style & Conventions

## 1. General Principles

- Prefer readable code over clever code; keep functions focused.
- Prefer platform configuration over code: if Frappe's workflow, permissions, or
  field options can express it, don't write Python.
- Reuse Frappe utilities (`frappe.utils`) before rolling your own.
- No client scripts (`.js`) in v1 — stock Desk only.

## 2. Naming

- **DocTypes:** Title Case (`PhD Scholar`, `Meeting Record`).
- **Fields:** snake_case (`report_year`, `action_items`).
- **Controllers:** Frappe's rule — DocType name with spaces stripped
  (`PhDScholar`, `ProgressReport`); file/folder = scrubbed lowercase
  (`phd_scholar.py`).
- **Python functions/variables:** snake_case; **constants:** UPPER_SNAKE_CASE
  (see `ROLES` in install.py).
- **Module:** `Phd Tracker` in modules.txt → `phd_tracker` folder.

## 3. Folder Structure

```
phd_tracker/phd_tracker/doctype/<doctype>/     one folder per DocType:
    __init__.py, <doctype>.json (schema), <doctype>.py (controller)
```

Rules:
- Nothing lives outside its DocType folder except hooks.py, install.py,
  modules.txt, patches.txt.
- New DocTypes are added as folders, never as loose files.
- docs/ is documentation, never importable code.

## 4. Imports

- Standard library, then `frappe` / `frappe.utils` — nothing else (no third-party
  dependencies; adding one requires a stated reason).
- No wildcard imports; no imports inside functions unless breaking a cycle.

## 5. Controllers

- Controllers inherit `frappe.model.document.Document` and stay thin: pass unless
  a hook has a real job (`validate`, `on_submit`).
- Business logic that applies to every write of a DocType goes in its `validate()`;
  logic specific to a workflow action goes in `on_submit()` / the state transition.
- One behavior per method; no God-methods.

## 6. Error Handling

- Use: raise `frappe.ValidationError` (or `frappe.throw` with a user-facing
  message) — let Frappe surface it to Desk/API uniformly.
- Do not: swallow exceptions, return error strings, or `print()`.
- Fail loudly; this is compliance software — silent failure is the worst outcome.

## 7. Comments

- Explain why something exists, important tradeoffs, non-obvious behavior
  (e.g. `install.py`'s idempotence guards).
- `ponytail:` comments mark deliberate simplifications with a known ceiling and
  their upgrade path.
- Never comment what the code plainly says.

## 8. Logging

- Frappe's logger (`frappe.logger("phd_tracker")`) if app-level logging is ever
  needed; error paths already land in Frappe's error log.
- Never log credentials, tokens, or full document contents.

## 9. Formatting

- **Formatter:** tabs, one class per file, PEP 8 line length (Frappe house style).
- **Linter:** none configured yet — run `python3 -m py_compile` on touched files
  minimally; add flake8 at the bench setup if desired.
- **JSON:** 1-space indent in DocType files matches Frappe exports — keep it.

## 10. Do

- Keep DocType JSON in the repo as the single source of truth (never Desk-only edits).
- Make idempotent install/patch code (`db.exists` guards before inserts).
- Extend existing patterns: new milestone types go in the Select options; new
  roles in `ROLES`.
- Write in batches, not loops: no per-row INSERT/UPDATE loops — use bulk writes
  (multi-row insert / single batched statement), chunked to ≤1000 rows, inside
  one transaction. First consumer: seed fixtures.

## 11. Don't

- Don't add third-party Python dependencies.
- Don't write client scripts, print CSS tricks, or custom APIs before a feature
  requires them.
- Don't hand-edit data in the database — patches only.
- Don't commit `._*` AppleDouble files (exFAT junk; gitignored) or any
  `site_config.json`.