# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _, throw
from erpnext.accounts.party import get_party_account
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry

class PaymentEntry(PaymentEntry):

	def set_liability_account(self):
		# Auto setting liability account should only be done during 'draft' status
		if self.docstatus > 0 or self.payment_type == "Internal Transfer":
			return

		self.book_advance_payments_in_separate_party_account = False
		if self.party_type not in ("Customer", "Supplier"):
			self.is_opening = "No"
			return

		if not frappe.db.get_value(
			"Company", self.company, "book_advance_payments_in_separate_party_account"
		):
			self.is_opening = "No"
			return

		# Important to set this flag for the gl building logic to work properly
		self.book_advance_payments_in_separate_party_account = True
		account_type = frappe.get_value(
			"Account", {"name": self.party_account, "company": self.company}, "account_type"
		)

		if (account_type == "Payable" and self.party_type == "Customer") or (
			account_type == "Receivable" and self.party_type == "Supplier"
		):
			self.is_opening = "No"
			return

		if self.references:
			# custom
			allowed_types = frozenset(["Sales Order", "Purchase Order","Sales Invoice"])
			# end
			reference_types = set([x.reference_doctype for x in self.references])

			# If there are referencers other than `allowed_types`, treat this as a normal payment entry
			if reference_types - allowed_types:
				self.book_advance_payments_in_separate_party_account = False
				self.is_opening = "No"
				return

		accounts = get_party_account(self.party_type, self.party, self.company, include_advance=True)

		liability_account = accounts[1] if len(accounts) > 1 else None
		fieldname = (
			"default_advance_received_account"
			if self.party_type == "Customer"
			else "default_advance_paid_account"
		)

		if not liability_account:
			throw(
				_("Please set default {0} in Company {1}").format(
					frappe.bold(frappe.get_meta("Company").get_label(fieldname)), frappe.bold(self.company)
				)
			)

		self.set(self.party_account_field, liability_account)

		frappe.msgprint(
			_(
				"Book Advance Payments as Liability option is chosen. Paid From account changed from {0} to {1}."
			).format(
				frappe.bold(self.party_account),
				frappe.bold(liability_account),
			),
			alert=True,
		)