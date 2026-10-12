app_name = "phd_tracker"
app_title = "PhD Tracker"
app_publisher = "Vivek Jindal"
app_description = "Supervisor-scholar PhD workspace; UGC compliance paperwork as a byproduct"
app_email = "vivek@example.com"  # TODO: real contact before any deployment
app_license = "mit"

after_install = "phd_tracker.install.after_install"

# Compliance artifacts (PRD Feature 5): APR print format + milestone register query report.
# Synced into the site by `bench migrate` / `bench sync-fixtures`.
fixtures = [
	{"dt": "Print Format", "filters": [["name", "in", ["APR"]]]},
	{"dt": "Report", "filters": [["report_name", "in", ["Milestone Register"]]]},
]