# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

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

    
        