# AI Coding Agent Instructions

## 1. Project Context

- **Project:** PhD Tracker
- **Purpose:** Supervisor–scholar workspace for Indian university PhD programs on
  the Frappe framework. The daily-use layer (meetings, progress reports,
  milestones) is the product; UGC compliance paperwork is generated as a byproduct.
- **Primary Users:** PhD scholars, PhD supervisors, research office admins.
  The buyer (registrar/dean) gets PDF exports, never a login.

## 2. Source of Truth

Before any non-trivial change, read the relevant document in `docs/`:
PRD.md, DESIGN_SYSTEM.md, ARCHITECTURE.md, DATABASE.md, SECURITY.md,
CODE_STYLE.md, TESTING.md, UX_FLOWS.md.

Do not contradict these documents. If a requirement and reality conflict, identify
the conflict and ask — do not guess.

## 3. General Rules

- Understand the existing code before modifying it; this is a Frappe app —
  most behavior is DocType JSON and workflow config, not Python.
- Prefer platform config over code (see CODE_STYLE.md).
- No third-party Python dependencies. No client-side JS in v1.
- Enforce nothing in the UI that isn't enforced server-side (SECURITY.md).
- Do not invent business requirements; PRD.md non-goals are real non-goals.
- Never touch secrets; never commit `site_config.json`.
- This repository lives on an exFAT volume: `._*` AppleDouble files and
  `__pycache__` are junk — gitignored; never stage or edit them.

## 4. Planning

Before implementing a non-trivial task:
1. Read the relevant doc(s) above.
2. Read the DocType JSON(s) you will touch.
3. List affected files (schema JSON, controller, install/patches, docs, tests).
4. Decide: is this expressible in workflow/permissions/field options? If yes,
   no Python.
5. State a concise plan before writing.

## 5. Implementation

- Focused changes; preserve existing patterns (folders, naming, perm matrix).
- DocType JSON in the repo is the schema's source of truth — never make
  Desk-only edits.
- New DocTypes: folder with `__init__.py`, `<name>.json`, `<name>.py`; add to no
  registry (Frappe discovers folders) but keep modules.txt consistent.
- Data migrations go through `patches.txt` — never raw SQL against a site DB.

## 6. Validation

After implementation:
1. `python3 -m py_compile` touched `.py` files; `python3 -m json.tool` touched
   JSONs (bench commands in TESTING.md once a bench env exists).
2. Click-verify the affected UX flow in docs/UX_FLOWS.md if a bench is available.
3. Confirm no unrelated files changed (`git status`).
4. Report honestly: what was run, what was skipped, what's unresolved.

## 7. Documentation

Update docs/ when a change alters: product behavior (PRD), schema (DATABASE),
permissions (SECURITY), flows (UX_FLOWS), or conventions (CODE_STYLE). Keep the
change to the affected section — don't rewrite whole documents.

## 8. Conflict Handling

If docs conflict with each other or with the code: identify the conflict
explicitly and ask for a decision. Specific rules win over general intent.
Never resolve a conflict by silently implementing a third option.

## 9. Completion Criteria

A task is complete only when:
- The PRD acceptance criteria for the touched feature hold.
- Syntax/JSON checks pass; bench tests pass when a bench exists.
- No unintended files changed.
- Security matrix (SECURITY.md §2) still holds — including negative cases.
- Docs updated where behavior changed.