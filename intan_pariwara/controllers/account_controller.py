# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint, flt

from erpnext.accounts.party import get_party_account_currency
from erpnext.controllers.accounts_controller import get_payment_terms, get_taxes_and_charges

class AccountsController:
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

    def set_missing_lead_customer_details(self, for_validate=False):
        customer, lead = None, None
        if getattr(self, "customer", None):
            customer = self.customer
        elif self.doctype == "Opportunity" and self.party_name:
            if self.opportunity_from == "Customer":
                customer = self.party_name
            else:
                lead = self.party_name
        elif self.doctype == "Quotation" and self.party_name:
            if self.quotation_to == "Customer":
                customer = self.party_name
            elif self.quotation_to == "Lead":
                lead = self.party_name

        if customer:
            from erpnext.accounts.party import _get_party_details
            from intan_pariwara.controllers.queries import get_price_list_fund

            fetch_payment_terms_template = False
            if self.get("__islocal") or self.company != frappe.db.get_value(
                self.doctype, self.name, "company"
            ):
                fetch_payment_terms_template = True

            party_details = _get_party_details(
                customer,
                ignore_permissions=self.flags.ignore_permissions,
                doctype=self.doctype,
                company=self.company,
                posting_date=self.get("posting_date"),
                fetch_payment_terms_template=fetch_payment_terms_template,
                party_address=self.customer_address,
                shipping_address=self.shipping_address_name,
                company_address=self.get("company_address"),
            )
            if not self.meta.get_field("sales_team"):
                party_details.pop("sales_team")

            party_details.update(
                get_price_list_fund(
                    self.company, self.customer, self.fund_source, self.seller, self.transaction_type, self.produk_inti_type
                )
            )
            
            self.update_if_missing(party_details)

        elif lead:
            from erpnext.crm.doctype.lead.lead import get_lead_details

            self.update_if_missing(
                get_lead_details(
                    lead,
                    posting_date=self.get("transaction_date") or self.get("posting_date"),
                    company=self.company,
                )
            )

        if self.get("taxes_and_charges") and not self.get("taxes") and not for_validate:
            taxes = get_taxes_and_charges("Sales Taxes and Charges Template", self.taxes_and_charges)
            for tax in taxes:
                self.append("taxes", tax)
                    		       
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