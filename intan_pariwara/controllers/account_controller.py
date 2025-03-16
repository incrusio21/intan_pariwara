# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint, flt

from erpnext.accounts.party import get_party_account_currency
from erpnext.controllers.accounts_controller import get_payment_terms

class AccountsController:
    def onload(self):
        self.set_onload(
            "make_payment_via_journal_entry",
            frappe.db.get_single_value("Accounts Settings", "make_payment_via_journal_entry"),
        )

        if self.is_new():
            relevant_docs = (
                "Pre Order",
                "Quotation",
                "Purchase Order",
                "Sales Order",
                "Purchase Invoice",
                "Sales Invoice",
            )
            if self.doctype in relevant_docs:
                self.set_payment_schedule()
                    
    def validate_all_documents_schedule(self):
        if self.doctype in ("Sales Invoice", "Purchase Invoice"):
            self.validate_invoice_documents_schedule()
        elif self.doctype in ("Pre Order","Quotation", "Purchase Order", "Sales Order"):
            self.validate_non_invoice_documents_schedule()

    def set_payment_schedule(self):
        if (self.doctype == "Sales Invoice" and self.is_pos) or self.get("is_opening") == "Yes":
            self.payment_terms_template = ""
            return

        party_account_currency = self.get("party_account_currency")
        if not party_account_currency:
            party_type, party = self.get_party()

            if party_type and party:
                party_account_currency = get_party_account_currency(party_type, party, self.company)

        posting_date = self.get("bill_date") or self.get("posting_date") or self.get("transaction_date")
        date = self.get("due_date") or self.get("payment_date")
        due_date = date or posting_date

        base_grand_total = self.get("base_rounded_total") or self.base_grand_total
        grand_total = self.get("rounded_total") or self.grand_total
        automatically_fetch_payment_terms = 0

        if self.doctype in ("Sales Invoice", "Purchase Invoice"):
            base_grand_total = base_grand_total - flt(self.base_write_off_amount)
            grand_total = grand_total - flt(self.write_off_amount)
            po_or_so, doctype, fieldname = self.get_order_details()
            automatically_fetch_payment_terms = cint(
                frappe.db.get_single_value("Accounts Settings", "automatically_fetch_payment_terms")
            )

        if self.get("total_advance"):
            if party_account_currency == self.company_currency:
                base_grand_total -= self.get("total_advance")
                grand_total = flt(
                    base_grand_total / self.get("conversion_rate"), self.precision("grand_total")
                )
            else:
                grand_total -= self.get("total_advance")
                base_grand_total = flt(
                    grand_total * self.get("conversion_rate"), self.precision("base_grand_total")
                )

        if not self.get("payment_schedule"):
            if (
                self.doctype in ["Sales Invoice", "Purchase Invoice"]
                and automatically_fetch_payment_terms
                and self.linked_order_has_payment_terms(po_or_so, fieldname, doctype)
            ):
                self.fetch_payment_terms_from_order(po_or_so, doctype)
                if self.get("payment_terms_template"):
                    self.ignore_default_payment_terms_template = 1
            elif self.get("payment_terms_template"):
                data = get_payment_terms(
                    self.payment_terms_template, posting_date, grand_total, base_grand_total
                )
                for item in data:
                    self.append("payment_schedule", item)
            elif self.doctype not in ["Purchase Receipt"]:
                data = dict(
                    due_date=due_date,
                    invoice_portion=100,
                    payment_amount=grand_total,
                    base_payment_amount=base_grand_total,
                )
                self.append("payment_schedule", data)

        allocate_payment_based_on_payment_terms = frappe.db.get_value(
            "Payment Terms Template", self.payment_terms_template, "allocate_payment_based_on_payment_terms"
        )

        if not (
            automatically_fetch_payment_terms
            and allocate_payment_based_on_payment_terms
            and self.linked_order_has_payment_terms(po_or_so, fieldname, doctype)
        ):
            for d in self.get("payment_schedule"):
                if d.invoice_portion:
                    d.payment_amount = flt(
                        grand_total * flt(d.invoice_portion) / 100, d.precision("payment_amount")
                    )
                    d.base_payment_amount = flt(
                        base_grand_total * flt(d.invoice_portion) / 100, d.precision("base_payment_amount")
                    )
                    d.outstanding = d.payment_amount
                elif not d.invoice_portion:
                    d.base_payment_amount = flt(
                        d.payment_amount * self.get("conversion_rate"), d.precision("base_payment_amount")
                    )
        else:
            self.fetch_payment_terms_from_order(po_or_so, doctype)
            self.ignore_default_payment_terms_template = 1
			       
    def calculate_taxes_and_totals(self):
        from intan_pariwara.controllers.taxes_and_totals import calculate_taxes_and_totals

        calculate_taxes_and_totals(self)

        if self.doctype in (
            "Sales Order",
            "Delivery Note",
            "Sales Invoice",
            "POS Invoice",
        ):
            self.calculate_commission()
            self.calculate_contribution()