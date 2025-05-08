# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _, throw
from erpnext.accounts.party import get_party_account
from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry
from frappe.utils import getdate, nowdate

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
			allowed_types = frozenset(["Sales Order", "Purchase Order", "Sales Invoice"])
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

	def add_party_gl_entries(self, gl_entries):
		if not self.party_account:
			return

		advance_payment_doctypes = frappe.get_hooks("advance_payment_doctypes")

		if self.payment_type == "Receive":
			against_account = self.paid_to
		else:
			against_account = self.paid_from

		party_account_type = frappe.db.get_value("Party Type", self.party_type, "account_type")

		party_gl_dict = self.get_gl_dict(
			{
				"account": self.party_account,
				"party_type": self.party_type,
				"party": self.party,
				"against": against_account,
				"account_currency": self.party_account_currency,
				"cost_center": self.cost_center,
			},
			item=self,
		)

		for d in self.get("references"):
			# re-defining dr_or_cr for every reference in order to avoid the last value affecting calculation of reverse
			dr_or_cr = "credit" if self.payment_type == "Receive" else "debit"
			cost_center = self.cost_center
			if d.reference_doctype == "Sales Invoice" and not cost_center:
				cost_center = frappe.db.get_value(d.reference_doctype, d.reference_name, "cost_center")

			gle = party_gl_dict.copy()

			allocated_amount_in_company_currency = self.calculate_base_allocated_amount_for_reference(d)

			if (
				d.reference_doctype in ["Sales Invoice", "Purchase Invoice"]
				and d.allocated_amount < 0
				and (
					(party_account_type == "Receivable" and self.payment_type == "Pay")
					or (party_account_type == "Payable" and self.payment_type == "Receive")
				)
			):
				# reversing dr_cr because because it will get reversed in gl processing due to negative amount
				dr_or_cr = "debit" if dr_or_cr == "credit" else "credit"

			gle.update(
				self.get_gl_dict(
					{
						"account": d.account_from or self.party_account,
						"party_type": self.party_type,
						"party": self.party,
						"against": against_account,
						"account_currency": self.party_account_currency,
						"cost_center": cost_center,
						dr_or_cr + "_in_account_currency": d.allocated_amount,
						dr_or_cr: allocated_amount_in_company_currency,
						dr_or_cr + "_in_transaction_currency": d.allocated_amount
						if self.transaction_currency == self.party_account_currency
						else allocated_amount_in_company_currency / self.transaction_exchange_rate,
					},
					item=self,
				)
			)

			if self.book_advance_payments_in_separate_party_account:
				if d.reference_doctype in advance_payment_doctypes:
					# Upon reconciliation, whole ledger will be reposted. So, reference to SO/PO is fine
					gle.update(
						{
							"against_voucher_type": d.reference_doctype,
							"against_voucher": d.reference_name,
						}
					)
				else:
					# Do not reference Invoices while Advance is in separate party account
					gle.update({"against_voucher_type": self.doctype, "against_voucher": self.name})
			else:
				gle.update(
					{
						"against_voucher_type": d.reference_doctype,
						"against_voucher": d.reference_name,
					}
				)

			gl_entries.append(gle)

		if self.unallocated_amount:
			dr_or_cr = "credit" if self.payment_type == "Receive" else "debit"
			exchange_rate = self.get_exchange_rate()
			base_unallocated_amount = self.unallocated_amount * exchange_rate

			gle = party_gl_dict.copy()

			gle.update(
				self.get_gl_dict(
					{
						"account": self.party_account,
						"party_type": self.party_type,
						"party": self.party,
						"against": against_account,
						"account_currency": self.party_account_currency,
						"cost_center": self.cost_center,
						dr_or_cr + "_in_account_currency": self.unallocated_amount,
						dr_or_cr + "_in_transaction_currency": self.unallocated_amount
						if self.party_account_currency == self.transaction_currency
						else base_unallocated_amount / self.transaction_exchange_rate,
						dr_or_cr: base_unallocated_amount,
					},
					item=self,
				)
			)
			if self.book_advance_payments_in_separate_party_account:
				gle.update(
					{
						"against_voucher_type": "Payment Entry",
						"against_voucher": self.name,
					}
				)
			gl_entries.append(gle)

	def add_advance_gl_for_reference(self, gl_entries, invoice):
		args_dict = {
			"party_type": self.party_type,
			"party": self.party,
			"account_currency": self.party_account_currency,
			"cost_center": self.cost_center,
			"voucher_type": "Payment Entry",
			"voucher_no": self.name,
			"voucher_detail_no": invoice.name,
		}

		if invoice.reconcile_effect_on:
			posting_date = invoice.reconcile_effect_on
		else:
			# For backwards compatibility
			# Supporting reposting on payment entries reconciled before select field introduction
			if self.advance_reconciliation_takes_effect_on == "Advance Payment Date":
				posting_date = self.posting_date
			elif self.advance_reconciliation_takes_effect_on == "Oldest Of Invoice Or Advance":
				date_field = "posting_date"
				if invoice.reference_doctype in ["Sales Order", "Purchase Order"]:
					date_field = "transaction_date"
				posting_date = frappe.db.get_value(
					invoice.reference_doctype, invoice.reference_name, date_field
				)

				if getdate(posting_date) < getdate(self.posting_date):
					posting_date = self.posting_date
			elif self.advance_reconciliation_takes_effect_on == "Reconciliation Date":
				posting_date = nowdate()
			frappe.db.set_value("Payment Entry Reference", invoice.name, "reconcile_effect_on", posting_date)

		dr_or_cr, account = self.get_dr_and_account_for_advances(invoice)
		base_allocated_amount = self.calculate_base_allocated_amount_for_reference(invoice)
		args_dict["account"] = account
		args_dict[dr_or_cr] = base_allocated_amount
		args_dict[dr_or_cr + "_in_account_currency"] = invoice.allocated_amount
		args_dict[dr_or_cr + "_in_transaction_currency"] = (
			invoice.allocated_amount
			if self.party_account_currency == self.transaction_currency
			else base_allocated_amount / self.transaction_exchange_rate
		)

		args_dict.update(
			{
				"against_voucher_type": invoice.reference_doctype,
				"against_voucher": invoice.reference_name,
				"posting_date": posting_date,
			}
		)
		gle = self.get_gl_dict(
			args_dict,
			item=self,
		)
		gl_entries.append(gle)

		args_dict[dr_or_cr] = 0
		args_dict[dr_or_cr + "_in_account_currency"] = 0
		dr_or_cr = "debit" if dr_or_cr == "credit" else "credit"
		args_dict["account"] = invoice.account_from or self.party_account
		args_dict[dr_or_cr] = base_allocated_amount
		args_dict[dr_or_cr + "_in_account_currency"] = invoice.allocated_amount
		args_dict[dr_or_cr + "_in_transaction_currency"] = (
			invoice.allocated_amount
			if self.party_account_currency == self.transaction_currency
			else base_allocated_amount / self.transaction_exchange_rate
		)
		args_dict.update(
			{
				"against_voucher_type": "Payment Entry",
				"against_voucher": self.name,
			}
		)
		gle = self.get_gl_dict(
			args_dict,
			item=self,
		)
		gl_entries.append(gle)