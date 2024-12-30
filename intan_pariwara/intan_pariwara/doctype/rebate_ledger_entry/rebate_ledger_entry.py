# Copyright (c) 2024, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from erpnext.accounts.general_ledger import toggle_debit_credit_if_negative
from erpnext.accounts.utils import _delete_accounting_ledger_entries

class RebateLedgerEntry(Document):
	def validate(self):
		self.create_or_update_journal()
	
	def create_or_update_journal(self):
		if self.rebate_je_entry:
			jv = frappe.get_doc("Journal Entry", self.rebate_je_entry)
		else:
			jv = frappe.new_doc("Journal Entry")

		jv.company = self.company
		jv.posting_date = self.posting_date

		jv.set("accounts", [
			{
				"account": self.account_from,
				"debit_in_account_currency": self.rebate_total
			},
			{
				"account": self.account_to,
				"credit_in_account_currency": self.rebate_total
			}
		])

		jv.flags.ignore_permissions = 1

		if self.rebate_je_entry:
			jv.db_update_all()
			expected_gle = toggle_debit_credit_if_negative(jv.get_gl_entries())
			if expected_gle:
				_delete_accounting_ledger_entries("Journal Entry", jv)
				jv.make_gl_entries(gl_entries=expected_gle)
		else:
			jv.submit()
			self.db_set("rebate_je_entry", jv.name)

	def after_delete(self):
		if not self.rebate_je_entry:
			return
		
		jv = frappe.get_doc("Journal Entry", self.rebate_je_entry)
		if jv.docstatus == 1:
			jv.cancel()

		jv.delete(delete_permanently=True)

def make_rebate_ledger_entry(
	company,
	voucher_type,
	voucher_no,
	posting_date,
	account_from,
	account_to,
	rebate_total
):
	rle = frappe.new_doc("Rebate Ledger Entry")
	rle.company = company
	rle.posting_date = posting_date
	rle.account_from = account_from
	rle.account_to = account_to

	rle.voucher_type = voucher_type
	rle.voucher_no = voucher_no

	rle.rebate_total = rebate_total
	rle.save()