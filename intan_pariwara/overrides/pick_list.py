from erpnext.stock.doctype.pick_list.pick_list import PickList
import frappe
from frappe import _, _dict
from frappe.query_builder.functions import Sum, Coalesce
from frappe.utils import flt

class PickList(PickList):
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