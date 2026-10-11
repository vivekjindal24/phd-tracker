# PhD Tracker

Supervisor–scholar workspace for Indian university PhD programs, built on the
[Frappe framework](https://frappeframework.com). The daily-use layer (meetings,
progress reports, milestone approvals) is the product; UGC compliance paperwork
(UGC 2022 PhD Regulations, as amended March 2024) falls out as a byproduct.

Status: **v0.0.1 — app scaffold, not yet installed on a bench site.**

## Why this shape

Incumbent Indian products (Pegado, Unity, Assessfy, Contineo) are
administration/compliance tools — forms the research office opens a few times
a year. None of them own the layer supervisors and scholars touch weekly.
This app starts from that layer and generates compliance artifacts from it,
so adoption pulls itself instead of being mandated.

Three roles at launch. Everyone else (HoD, Dean, VC, committees) gets PDF
exports and email — deliberately no portals in v1.

## DocTypes

| DocType | Purpose |
|---|---|
| PhD Scholar | Scholar profile, supervisor assignment, current stage, GitHub repo URL |
| PhD Supervisor | Faculty profile, UGC supervision cap (8/6/4 by designation) |
| Meeting Record | Supervisor–scholar meeting log: agenda, minutes, action items, next date |
| Progress Report | Six-monthly APR — runs through the approval workflow |
| PhD Milestone | RDC/DPGC-style approvals with resolution number, date, approval body |

## Workflow: Progress Report Approval

Created in `install.py` on app install:

```
Draft --(Scholar: Submit Report)--> Submitted
Submitted --(Supervisor: Approve)--> Approved       (doc_status 1)
Submitted --(Supervisor: Send Back)--> Rejected
Rejected --(Scholar: Revise and Resubmit)--> Draft
```

## Setup (once a bench environment exists)

Frappe v15 needs Python 3.10–3.13 — the system Python 3.14 is not supported.
Keep the bench on your internal disk; this repo can stay on the external volume.

```bash
brew install mariadb redis pyenv
pyenv install 3.12 && pyenv local 3.12
pipx install frappe-bench

bench init phd-dev --frappe-branch version-15
cd phd-dev
bench get-app /Volumes/VivekJindal/phd-tracker
bench new-site phd.local --db-root-password <pw> --admin-password <pw>
bench --site phd.local install-app phd_tracker
bench start
```

Installing the app creates the three roles (PhD Scholar, PhD Supervisor,
Research Office Admin) and the progress-report workflow.

## Deliberately NOT in v1

Admissions, coursework grading, grants/ledger, plagiarism-check API
integration (record similarity scores manually for now), NAAC/NIRF exports,
Shodhganga sync, GitHub activity mirroring, VC dashboards, fine-grained
per-document owner permissions. Each waits for a paying university to pull it.

## Roadmap

1. Exports pack: UGC-format APR PDF + RDC milestone register per scholar
2. Per-scholar timeline view (meetings + reports + milestones on one page)
3. Read-only GitHub activity mirror (commit streak per scholar)
4. Fine-grained ownership rules (scholars see only their own docs)