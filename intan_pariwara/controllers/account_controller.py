# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint, flt
from frappe.query_builder import Criterion
from frappe.query_builder.custom import ConstantColumn
from frappe.query_builder.functions import IfNull

from erpnext.accounts.party import get_party_account_currency
from erpnext.controllers.accounts_controller import get_payment_terms, get_taxes_and_charges

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

            relasi = self.relasi if party_details.get("has_relation") else None
            party_details.update(
                get_price_list_fund(
                    self.company, customer, relasi, self.fund_source, self.seller, self.transaction_type, self.produk_inti_type
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

def get_advance_payment_entries(
    party_type,
	party,
	party_account,
	order_doctype,
	order_list=None,
	default_advance_account=None,
	include_unallocated=True,
	against_all_orders=False,
	limit=None,
	condition=None,
):
    payment_entries = []
    payment_entry = frappe.qb.DocType("Payment Entry")

    if order_list or against_all_orders:
        payment_ref = frappe.qb.DocType("Payment Entry Reference")

        order_type = [
            {"use_advance_account": False, "account_from": ""},
            {"use_advance_account": True, "account_from": default_advance_account}
        ]

        for cond in order_type:
            q = get_common_query(
                payment_entry,
                party_type,
                party,
                party_account,
                default_advance_account,
                limit,
                condition,
                cond.get("use_advance_account")
            )
            
            q = (
                q.inner_join(payment_ref)
                .on(payment_entry.name == payment_ref.parent)
                .select(
                    payment_ref.allocated_amount.as_("amount"),
                    payment_ref.name.as_("reference_row"),
                    payment_ref.reference_name.as_("against_order"),
                    payment_entry.book_advance_payments_in_separate_party_account,
                )
                .where(
                    (payment_ref.reference_doctype == order_doctype)
                    & (IfNull(payment_ref.account_from, "") == cond.get("account_from"))
                )
            )
            
            if order_list:
                q = q.where(payment_ref.reference_name.isin(order_list))
            
            payment_entries += list(q.run(as_dict=True))

    if include_unallocated:
        q = get_common_query(
            payment_entry,
            party_type,
            party,
            party_account,
            default_advance_account,
            limit,
            condition,
        )
        q = q.select((payment_entry.unallocated_amount).as_("amount"))
        q = q.where(payment_entry.unallocated_amount > 0)

        unallocated = list(q.run(as_dict=True))
        payment_entries += unallocated

    return payment_entries

def get_common_query(
    payment_entry,
	party_type,
	party,
	party_account,
	default_advance_account,
	limit,
	condition,
    no_account=False
):
    account_type = frappe.db.get_value("Party Type", party_type, "account_type")
    payment_type = "Receive" if account_type == "Receivable" else "Pay"

    q = (
        frappe.qb.from_(payment_entry)
        .select(
            ConstantColumn("Payment Entry").as_("reference_type"),
            (payment_entry.name).as_("reference_name"),
            payment_entry.posting_date,
            (payment_entry.remarks).as_("remarks"),
            (payment_entry.book_advance_payments_in_separate_party_account),
        )
        .where(payment_entry.payment_type == payment_type)
        .where(payment_entry.party_type == party_type)
        .where(payment_entry.party == party)
        .where(payment_entry.docstatus == 1)
    )

    field = "paid_from" if payment_type == "Receive" else "paid_to"

    q = q.select((payment_entry[f"{field}_account_currency"]).as_("currency"))
    if not no_account:
        q = q.select(payment_entry[field])
        account_condition = payment_entry[field].isin(party_account)
        if default_advance_account:
            q = q.where(
                account_condition
                | (
                    (payment_entry[field] == default_advance_account)
                    & (payment_entry.book_advance_payments_in_separate_party_account == 1)
                )
            )

        else:
            q = q.where(account_condition)

    if payment_type == "Receive":
        q = q.select((payment_entry.source_exchange_rate).as_("exchange_rate"))
    else:
        q = q.select((payment_entry.target_exchange_rate).as_("exchange_rate"))

    if condition:
        # conditions should be built as an array and passed as Criterion
        common_filter_conditions = []

        common_filter_conditions.append(payment_entry.company == condition["company"])
        if condition.get("name", None):
            common_filter_conditions.append(payment_entry.name.like(f"%{condition.get('name')}%"))

        if condition.get("from_payment_date"):
            common_filter_conditions.append(payment_entry.posting_date.gte(condition["from_payment_date"]))

        if condition.get("to_payment_date"):
            common_filter_conditions.append(payment_entry.posting_date.lte(condition["to_payment_date"]))

        if condition.get("get_payments") is True:
            if condition.get("cost_center"):
                common_filter_conditions.append(payment_entry.cost_center == condition["cost_center"])

            if condition.get("accounting_dimensions"):
                for field, val in condition.get("accounting_dimensions").items():
                    common_filter_conditions.append(payment_entry[field] == val)

            if condition.get("minimum_payment_amount"):
                common_filter_conditions.append(
                    payment_entry.unallocated_amount.gte(condition["minimum_payment_amount"])
                )

            if condition.get("maximum_payment_amount"):
                common_filter_conditions.append(
                    payment_entry.unallocated_amount.lte(condition["maximum_payment_amount"])
                )
        q = q.where(Criterion.all(common_filter_conditions))

    q = q.orderby(payment_entry.posting_date)
    q = q.limit(limit) if limit else q

    return q