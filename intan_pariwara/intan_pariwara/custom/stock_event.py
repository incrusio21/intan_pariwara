# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

def update_status_qr_code(self, method):
    qr_code = set()
    from intan_pariwara.utils.qr_code import get_qr_code_nos

    for d in self.items:
        if not d.get("qr_code_no"):
            continue
        
        for qr_name in get_qr_code_nos(d.qr_code_no):
            qr_code.add(qr_name)

    for qr in list(qr_code):
        frappe.get_doc("Qr Code Packing Bundle", qr).set_status(db_update=True)
