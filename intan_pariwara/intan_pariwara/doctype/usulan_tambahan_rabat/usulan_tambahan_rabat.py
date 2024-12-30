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
		from intan_pariwara.intan_pariwara.doctype.rebate_ledger_entry.rebate_ledger_entry import make_rebate_ledger_entry

		make_rebate_ledger_entry(
			self.company,
			self.doctype,
			self.name,
			self.posting_date,
			self.rebate_account_from,
			self.rebate_account_to,
			self.rebate_total,
		)
	
	def on_cancel(self):
		self.remove_rebate_entry()

	def on_trash(self):
		self.remove_rebate_entry(True)

	def remove_rebate_entry(self, remove=False):
		rle_list = frappe.get_list("Rebate Ledger Entry", filters={"voucher_type": self.doctype, "voucher_no": self.name}, pluck="name")
		for rle in rle_list:
			doc = frappe.get_doc("Rebate Ledger Entry", rle)
			if not remove:
				doc.is_cancelled = 1
				doc.save()
			else:
				doc.delete()