# Testing

## 1. Testing Goals

Critical functionality to verify before any pilot demo:
- Progress Report approval workflow (role-gated transitions, correct doc_status)
- Permissions matrix (a scholar cannot approve; a supervisor cannot manage the
  directory; etc.)
- Install correctness (fresh site → roles + workflow exist, app is re-installable)

## 2. Test Types

### Unit Testing
DocType controller behavior: `on_submit` sets `approved_on`; future `validate()`
rules (duplicate APR, supervision cap).

### Integration Testing
Frappe's test framework with a test site: create scholar + supervisor + report
records, drive workflow transitions as different roles, assert states and
permission denials.

### End-to-End Testing
Until a bench environment exists: manual click-through of the flows in
UX_FLOWS.md with all three roles. After pilot deployment: Playwright against the
instance (deferred until then).

## 3. Testing Tools

- Unit + Integration: Frappe's built-in `test_records`/`FrappeTestCase` (or the
  v15 `IntegrationTestCase`) — runs via bench.
- E2E: manual checklist now; Playwright when there's a deployed instance to click.

## 4. Test File Structure

Standard Frappe placement — tests live beside the controller:

```
phd_tracker/phd_tracker/doctype/progress_report/test_progress_report.py
```

(When a test needs cross-DocType setup, it still lives in the primary DocType's
test file — no shared fixtures layer yet.)

## 5. Critical User Flows

### Flow A — Scholar submits APR
1. As admin: create supervisor + scholar (linked).
2. As scholar: create Progress Report (year, period, summary), Save.
3. Click Submit Report.
**Expected:** state Submitted; supervisor cannot edit summary (allow_edit).
**Failure to verify:** workflow role gate broken.

### Flow B — Supervisor approves / sends back
1. As supervisor: open the submitted report, add comment.
2. Approve → doc_status 1, `approved_on` set today.
3. Repeat with Send Back → Rejected; scholar revises, resubmits.
**Expected:** state Approved/Rejected per action; version history records both.

### Flow C — Research office records RDC milestone
1. As admin: create PhD Milestone (Proposal Approval, RDC, resolution no/date).
2. View as scholar: read-only.
**Expected:** milestone visible to scholar, not editable.

## 6. Coverage

- **Target:** every controller hook and permission boundary exercised; no
  percentage theater — this app is mostly config, and config is tested by the
  flows above.
- **Prioritize:** workflow transitions (compliance correctness) > permission
  denials > controller hooks > install idempotence.

## 7. Commands

```bash
# Test (on a bench with a test site):
bench --site <test-site> run-tests --app phd_tracker

# Lint / syntax (pre-bench):
python3 -m py_compile $(git ls-files '*.py')
python3 -m json.tool <doctype>.json   # per changed JSON

# Build / install (the real smoke test):
bench --site <site> install-app phd_tracker
bench --site <site> migrate
```

## 8. Definition of Done

- [ ] Tests pass (`run-tests --app phd_tracker`)
- [ ] App installs cleanly on a fresh site; migrate is re-runnable
- [ ] Flows A–C click-verified with all three roles
- [ ] Permission denials checked (negative tests)
- [ ] No unrelated files changed
- [ ] Docs updated if behavior changed