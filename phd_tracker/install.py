import frappe

ROLES = ["PhD Scholar", "PhD Supervisor", "Research Office Admin"]


def after_install():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)

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