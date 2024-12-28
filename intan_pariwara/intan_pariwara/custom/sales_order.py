# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

def create_and_delete_rebate(self, method):
    if not self.apply_rebate:
        return
    
    if self.get("custom_rebate_entry"):
        jv = frappe.get_doc("Journal Entry", self.custom_rebate_entry)
        if method == "on_cancel":
            jv.cancel()
        elif method == "after_delete":
            jv.delete(delete_permanently=True)

    if method == "on_submit":
        if not (self.rebate_account_from and self.rebate_account_to):
            frappe.throw("Select Rebate Account First")

        je = frappe.new_doc("Journal Entry")
        je.company = self.company
        je.posting_date = self.transaction_date
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

        self.db_set("custom_rebate_entry", je.name)
        self.reload()