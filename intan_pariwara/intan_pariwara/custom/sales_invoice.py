# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _, query_builder
from frappe.utils import date_diff, getdate
from frappe.query_builder import functions

class SalesInvoice:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        if self.method == "before_submit":
            self.validate_fund_source_account()
            self.validate_bad_debt()

    def validate_fund_source_account(self):
        if not self.doc.fund_source:
            return
        
        incoming_field, discount_field = "incoming_account", "discount_acount"
        # account yang di gunakan untuk return berbeda
        if self.doc.is_return:
            incoming_field = "return_incoming_account"
            discount_field = "return_discount_account"

        incoming_account, expense_account, discount_account = frappe.get_value("Fund Source Accounts", 
            {
                "parent": self.doc.fund_source,
                "company": self.doc.company,
                "transaction_type": self.doc.transaction_type,
            }, 
            [incoming_field, "expense_account", discount_field]) or ["", "", ""]
        
        if not (incoming_account or expense_account or discount_account):
            frappe.throw("Please insert Incoming, Expense adn Discount Account in Customer Fund Source first.")
        
        for d in self.doc.items:
            d.update({
                "incoming_account": incoming_account,
                "expense_account": expense_account,
                "discount_account": discount_account,
            })

    def validate_bad_debt(self):
        date_before_bad_debt = date_diff(self.doc.due_date, None)
        if date_before_bad_debt >= 0:
            return

        self.doc.bad_debt = 1
        self.doc.bad_debt_days = abs(date_before_bad_debt)

def create_and_delete_rebate(self, method):
    if not self.apply_rebate:
        return
    
    rle_list = frappe.get_list("Rebate Ledger Entry", filters={"voucher_type": self.doctype, "voucher_no": self.name}, pluck="name")
    for rle in rle_list:
        doc = frappe.get_doc("Rebate Ledger Entry", rle)
        if method == "on_cancel":
            doc.is_cancelled = 1
            doc.save()
        if method == "on_trash":
            doc.delete()
            
    if method == "on_submit":
        if not (self.rebate_account_from and self.rebate_account_to):
            frappe.throw("Select Rebate Account First")

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


def update_bad_debt_sales_invoice():
    """Updates bad debt for applicable invoices. Runs daily."""
    today = getdate()
    invoice = frappe.qb.DocType("Sales Invoice")

    conditions = (
        (invoice.docstatus == 1)
        & (invoice.outstanding_amount > 0)
        & (invoice.due_date < today)
    )
    
    datediff = query_builder.CustomFunction("DATEDIFF", ["cur_date", "due_date"])

    total_bad_debt_days = (
        datediff(functions.CurDate(), invoice.due_date)
    )

    frappe.qb.update(invoice).set("bad_debt", 1).set("bad_debt_days", total_bad_debt_days).where(conditions).run()
        