# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from erpnext.accounts.utils import get_fiscal_year

class StockEntry:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        if self.method == "on_submit":
            self.update_plafon_promosi()
            self.update_packing_qty()
        elif self.method == "on_cancel":
            self.update_plafon_promosi()
            self.update_packing_qty()

    def update_plafon_promosi(self):
        if self.doc.stock_entry_type not in ["Issue of Promotional Goods", "Receipt of Promotional Goods"]:
            return
        
        current_fiscal_year = get_fiscal_year(self.doc.posting_date, as_dict=True)
        
        promosi = frappe.get_doc("Plafon Promosi", {"fiscal_year": current_fiscal_year.name, "cabang": self.doc.promosi_branch}, for_update=1)
        promosi.set_remaining_plafon()

    def update_packing_qty(self):
        packing_list = {}

        for d in self.doc.get("items"):
            if d.packing_list:
                packing_list.setdefault(d.packing_list, []).append(d.packing_list_item)

        for pr, pr_item_rows in packing_list.items():
            if pr and pr_item_rows:
                pr_obj = frappe.get_doc("Packing List", pr)

                # if pr_obj.status in ["Stopped", "Cancelled"]:
                #     frappe.throw(
                #         _("{0} {1} is cancelled or stopped").format(_("Packing List"), pr),
                #         frappe.InvalidStatusError,
                #     )

                pr_obj.update_completed_qty(pr_item_rows)

@frappe.whitelist()
def detail_item_request(item, from_warehouse=None, to_warehouse=None):
    ress = {}
    fields = []
    if not from_warehouse:
        fields.append("from_warehouse as s_warehouse")

    if not to_warehouse:
        fields.append("warehouse as t_warehouse")

    if fields:
        ress.update(
            frappe.get_value("Material Request Item", {"name": item}, fields, as_dict=1)
        )

    return ress