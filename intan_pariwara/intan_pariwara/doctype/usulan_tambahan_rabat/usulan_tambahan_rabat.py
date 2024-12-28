# Copyright (c) 2024, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class UsulanTambahanRabat(Document):
	def validate(self):
		self.validate_rebate_account()

	def validate_rebate_account(self):
		if not (self.rebate_account_from and self.rebate_account_to):
			frappe.throw("Please Select Rebate Account First")

	def on_submit(self):
		self.create_rebate_entry()

	def create_rebate_entry(self):
		je = frappe.new_doc("Journal Entry")
		je.company = self.company
		je.posting_date = self.posting_date
		je.append("accounts", {
			"account": self.rebate_account_from,
			"debit_in_account_currency": self.rebate_total
		})

		je.append("accounts", {
			"account": self.rebate_account_to,
			"credit_in_account_currency": self.rebate_total
		})

		je.flags.ignore_permissions = 1
		je.submit()

		self.db_set("rebate_additional_entry", je.name)
		self.reload()
	
	def on_cancel(self):
		self.remove_rebate_entry()

	def after_delete(self):
		self.remove_rebate_entry(True)
	
	def remove_rebate_entry(self, remove=False):
		if not self.get("rebate_additional_entry"):
			return
		
		jv = frappe.get_doc("Journal Entry", self.rebate_additional_entry)
		if jv.docstatus == 1:
			jv.cancel()
		
		if remove:
			jv.delete(delete_permanently=True)
	