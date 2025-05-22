# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _

from erpnext.stock.doctype.pick_list.pick_list import (
    PickList, 
    filter_locations_by_picked_materials, get_available_item_locations_for_other_item
)
from frappe.utils import flt, get_link_to_form

from intan_pariwara.utils.data import get_bin_with_request

class PickList(PickList):
    def validate(self):
        self.set_purpose()
        self.set_branch()
        self.get_actual_qty()
        super().validate()

    def get_purpose_request(self):
        if not getattr(self, "_purpose_request", None):
            self._purpose_request = frappe.get_cached_doc("Purpose Request", self.pick_list_type)

        if not self._purpose_request:
            frappe.throw("Please set Purpose to Qr Code Bundling first")

        return self._purpose_request
        
    def set_purpose(self):
        self.purpose = self.get_purpose_request().get("pick_list_purpose")

    def set_branch(self):
        pr = self.get_purpose_request()
        doctype = ref_field = fields = ""
        match pr.request_to:
            case "Delivery Note":
                doctype, ref_field, fields = "Sales Order", self.locations[0].sales_order, "branch"
            case "Stock Entry": 
                doctype, ref_field, fields = "Material Request", self.material_request, "custom_branch"

        if not (doctype and ref_field and fields):
            frappe.throw("No reference documents exist for these items.")
            
        self.branch = frappe.get_value(doctype, ref_field, fields)

    def _get_pick_list_items(self, items):
        pi = frappe.qb.DocType("Pick List")
        pi_item = frappe.qb.DocType("Pick List Item")
        query = (
            frappe.qb.from_(pi)
            .inner_join(pi_item)
            .on(pi.name == pi_item.parent)
            .select(
                pi_item.item_code,
                pi_item.warehouse,
                pi_item.batch_no,
                pi_item.serial_and_batch_bundle,
                pi_item.serial_no,
                pi_item.picked_qty > 0, pi_item.picked_qty,
            )
            .where(
                (pi_item.item_code.isin([x.item_code for x in items]))
                & (pi_item.picked_qty > 0)
                & (pi.status != "Completed")
                & (pi.status != "Cancelled")
                & (pi_item.docstatus != 2)
            )
        )

        if self.name:
            query = query.where(pi_item.parent != self.name)

        query = query.for_update()

        return query.run(as_dict=True)
    
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

    def get_actual_qty(self):  
        picked_items_details = self.get_picked_items_details(self.locations)
        for d in self.locations:
            picked_item_details = picked_items_details.get(d.item_code)

            locations = get_available_item_locations_for_other_item(
                d.item_code,
                [d.warehouse],
                self.company,
                self.consider_rejected_warehouses
            )
            
            if picked_item_details:
                locations = filter_locations_by_picked_materials(locations, picked_item_details)

            if not locations:
                frappe.throw("Row#{0}: Item {1} is picked in another Pick List.".format(d.idx, get_link_to_form("Item", d.item_code)))

            d.available_qty = flt(locations[0]["qty"] - d.picked_qty)

            bin_detail =  get_bin_with_request(d.item_code, d.warehouse)
            d.actual_qty = bin_detail.get("actual_qty", 0)
            d.projected_qty = bin_detail.get("projected_qty", 0)
            d.reserved_qty = bin_detail.get("reserved_qty", 0)
            d.request_qty = bin_detail.get("request_qty", 0)
                
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
            if d.picked_qty > 0:  # Hindari division by zero
                min_packing.append(d.packed_qty / d.picked_qty)

        # Update status berdasarkan rasio terkecil
        status = 'Completed' if min_packing and min(min_packing) >= 1 else 'Open'
        self.db_set("status", status)

