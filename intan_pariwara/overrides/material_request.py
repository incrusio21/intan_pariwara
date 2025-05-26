# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.stock.doctype.material_request.material_request import MaterialRequest

class MaterialRequest(MaterialRequest):
    def validate(self):
        self.set_material_request_type()
        super().validate()

    def set_material_request_type(self):
        self.material_request_type = frappe.db.get_value("Purpose Request", self.purpose, "purpose")

    def update_picking_status(self):
        total_picked_qty = 0.0
        total_qty = 0.0
        per_picked = 0.0

        total_picked = frappe._dict(frappe.db.sql("""
            SELECT material_request_item, SUM(picked_qty) 
                FROM `tabPick List Item` 
                WHERE material_request = %(detail_id)s AND docstatus = 1
                Group By material_request_item
            """, {"detail_id": self.name}))
        
        for mr_item in self.items:
            # Update picked_qty langsung ke database
            mr_item.db_set("picked_qty", total_picked.get(mr_item.name) or 0)

            total_picked_qty += flt(mr_item.picked_qty) if mr_item.stock_qty > mr_item.picked_qty else flt(mr_item.stock_qty)
            total_qty += flt(mr_item.stock_qty)

        if total_picked_qty and total_qty:
            per_picked = total_picked_qty / total_qty * 100

            pick_percentage = frappe.db.get_single_value("Stock Settings", "over_picking_allowance")
            if pick_percentage:
                total_qty += flt(total_qty) * (pick_percentage / 100)

            if total_picked_qty > total_qty:
                frappe.throw(
                    _(
                        "Total Picked Quantity {0} is more than ordered qty {1}. You can set the Over Picking Allowance in Stock Settings."
                    ).format(total_picked_qty, total_qty)
                )

        self.db_set("per_picked", flt(per_picked), update_modified=False)