import frappe

ROLES = ["PhD Scholar", "PhD Supervisor", "Research Office Admin"]

WORKFLOW_STATES = ["Draft", "Submitted", "Approved", "Rejected"]
WORKFLOW_ACTIONS = ["Submit Report", "Approve", "Send Back", "Revise and Resubmit"]

SEARCHABLE_DOCTYPES = [
	"PhD Scholar",
	"PhD Supervisor",
	"Progress Report",
	"PhD Milestone",
	"Meeting Record",
]


def _ensure_master(doctype, name_field, name):
	"""Create a simple master record if missing (idempotent)."""
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, name_field: name}).insert(ignore_permissions=True)


def after_install():
	_ensure_global_search_settings()

	for role in ROLES:
		_ensure_master("Role", "role_name", role)
	for state in WORKFLOW_STATES:
		_ensure_master("Workflow State", "workflow_state_name", state)
	for action in WORKFLOW_ACTIONS:
		_ensure_master("Workflow Action Master", "workflow_action_name", action)

	if not frappe.db.exists("Workflow", "Progress Report Approval"):
		frappe.get_doc(
			{
				"doctype": "Workflow",
				"workflow_name": "Progress Report Approval",
				"document_type": "Progress Report",
				"workflow_state_field": "workflow_state",
				"is_active": 1,
				"send_mail_alert": 0,
				"states": [
					{"state": "Draft", "doc_status": 0, "allow_edit": "PhD Scholar"},
					{"state": "Submitted", "doc_status": 0, "allow_edit": "PhD Supervisor"},
					{"state": "Approved", "doc_status": 1, "allow_edit": "Research Office Admin"},
					{"state": "Rejected", "doc_status": 0, "allow_edit": "PhD Scholar"},
				],
				"transitions": [
					{
						"state": "Draft",
						"action": "Submit Report",
						"next_state": "Submitted",
						"allowed": "PhD Scholar",
					},
					{
						"state": "Submitted",
						"action": "Approve",
						"next_state": "Approved",
						"allowed": "PhD Supervisor",
					},
					{
						"state": "Submitted",
						"action": "Send Back",
						"next_state": "Rejected",
						"allowed": "PhD Supervisor",
					},
					{
						"state": "Rejected",
						"action": "Revise and Resubmit",
						"next_state": "Draft",
						"allowed": "PhD Scholar",
					},
				],
			}
		).insert(ignore_permissions=True)


def _ensure_global_search_settings():
	"""Register our DocTypes in Global Search Settings so Desk search covers them."""
	settings = frappe.get_single("Global Search Settings")
	listed = {d.document_type for d in settings.allowed_in_global_search}
	missing = [dt for dt in SEARCHABLE_DOCTYPES if dt not in listed]
	if missing:
		for dt in missing:
			settings.append(
				"allowed_in_global_search",
				{"doctype": "Global Search DocType", "document_type": dt},
			)
		settings.save(ignore_permissions=True)