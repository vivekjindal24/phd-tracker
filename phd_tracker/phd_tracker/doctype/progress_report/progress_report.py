# Copyright (c) 2026 Vivek Jindal
# For license information, see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class ProgressReport(Document):
	def on_submit(self):
		# assignments made in on_submit are not persisted by the framework
		self.db_set("approved_on", nowdate())