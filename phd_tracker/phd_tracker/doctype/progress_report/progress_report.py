# Copyright (c) 2026 Vivek Jindal
# For license information, see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class ProgressReport(Document):
	def on_submit(self):
		self.approved_on = nowdate()