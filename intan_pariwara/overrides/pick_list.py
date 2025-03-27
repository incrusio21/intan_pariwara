# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Sum, Coalesce
from frappe.utils import flt

from erpnext.stock.doctype.pick_list.pick_list import PickList

class PickList(PickList):
    def update_sales_order_picking_status(self) -> None:
        sales_orders, material_reqs = [], []
        for row in self.locations:
            if row.sales_order and row.sales_order not in sales_orders:
                sales_orders.append(row.sales_order)

            if row.material_request and row.material_request not in material_reqs:
                material_reqs.append(row.material_request)

        for sales_order in sales_orders:
            frappe.get_doc("Sales Order", sales_order, for_update=True).update_picking_status()

        for material_req in material_reqs:
            frappe.get_doc("Material Request", material_req, for_update=True).update_picking_status()

    def update_packed_qty(self):

        min_packing = []
        for d in self.locations:
            # Ambil total qty dari kedua tabel sekaligus
            total_packed = frappe.db.sql("""
                SELECT 
                    COALESCE((
                        SELECT SUM(qty) 
                        FROM `tabPacking List Item Retail` 
                        WHERE document_detail = %(detail_id)s AND docstatus = 1
                    ), 0) + 
                    COALESCE((
                        SELECT SUM(qty) 
                        FROM `tabPacking List Item` 
                        WHERE document_detail = %(detail_id)s AND docstatus = 1
                    ), 0)
                """, {"detail_id": d.name})[0][0] or 0.0

            # Update packed_qty langsung ke database
            d.db_set("packed_qty", total_packed)
            
            # Hitung rasio packing
            if d.qty > 0:  # Hindari division by zero
                min_packing.append(d.packed_qty / d.qty)

        # Update status berdasarkan rasio terkecil
        status = 'Completed' if min_packing and min(min_packing) >= 1 else 'Open'
        self.db_set("status", status)