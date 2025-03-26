# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt

from intan_pariwara.utils.qr_code import get_qr_code_nos

def set_qr_code(self, method):
    qr_code, total_qty = set(), 0

    for d in self.items:
        total_qty += d.qty
        if not d.get("qr_code_no"):
            continue
        
        for qr_name in get_qr_code_nos(d.qr_code_no):
            qr_code.add(qr_name)

    self.qr_code = "\n".join(list(qr_code))
    self.total_koli = len(qr_code)
    self.total_qty = flt(total_qty, self.precision("total_qty"))

def update_status_qr_code(self, method):
    for qr in get_qr_code_nos(self.qr_code):
        frappe.get_doc("Qr Code Packing Bundle", qr, for_update=1).set_status(db_update=True)
