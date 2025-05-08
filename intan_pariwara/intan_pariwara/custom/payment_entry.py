# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

def set_reference_account_from(self, method):
    ref_doc, ref_account = {}, {}
    for r in self.references:
        # pastikan doctype memiliki field advance account
        meta = ref_doc.setdefault(r.reference_doctype, frappe.get_meta(r.reference_doctype).get_field("advanced_account"))
        if not meta:
            continue
         
        if not r.get("account_from"):
            # simpan nilai account pada object supaya tidak memanggil db untuk document yang sama 
            account = ref_account.setdefault(
                (r.reference_doctype, r.reference_name), 
                frappe.get_value(r.reference_doctype, r.reference_name, "advanced_account")
            )

            r.set("account_from", account)