# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt

from intan_pariwara.utils.data import get_bin_with_request

def update_pre_order_status(self, method):
    if self.purpose not in ["Siplah Titipan"]:
        return

    frappe.get_doc("Pre Order", self.pre_order, for_update=True).update_po_status()

@frappe.whitelist()
def make_packing_list(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.purpose = "Material Request"
        target.run_method("set_missing_values")

    def update_item(obj, target, source_parent):
        target.qty = flt(obj.qty) - flt(obj.packed_qty)
        
    doclist = get_mapped_doc(
        "Material Request",
        source_name,
        {
            "Material Request": {
                "doctype": "Packing List",
                "field_map": {
                    "name": "doc_name",
                    "letter_head": "letter_head"
                },
                "validation": {"docstatus": ["=", 1]},
            }
        },
        target_doc,
        set_missing_values,
    )

    return doclist

@frappe.whitelist()
def create_pick_list(source_name, target_doc=None):
    
    def postprocess(source, target):
        target.parent_warehouse = source.set_from_warehouse \
            if source.material_request_type == "Material Transfer" else \
            source.set_warehouse

    def update_item_quantity(source, target, source_parent) -> None:
        qty_to_be_picked = flt(source.stock_qty) - flt(source.picked_qty)

        target.stock_qty = qty_to_be_picked 
        target.qty = qty_to_be_picked / flt(source.conversion_factor)
        bin_detail =  get_bin_with_request(target.item_code, target.warehouse)
        target.actual_qty = bin_detail.get("actual_qty", 0)
        target.projected_qty = bin_detail.get("projected_qty", 0)
        target.reserved_qty = bin_detail.get("reserved_qty", 0)
        target.request_qty = bin_detail.get("request_qty", 0)

    def should_pick_order_item(item) -> bool:
        return (
            abs(item.picked_qty) < abs(item.qty)
        )

    doc = get_mapped_doc(
        "Material Request",
        source_name,
        {
            "Material Request": {
                "doctype": "Pick List",
                "field_map": {
                    "purpose": "pick_list_type",
                    "material_request_type": "purpose"
                },
                "validation": {"docstatus": ["=", 1]},
            },
            "Material Request Item": {
                "doctype": "Pick List Item",
                "field_map": {"name": "material_request_item"},
                "postprocess": update_item_quantity,
                "condition": should_pick_order_item,
            },
        },
        target_doc,
        postprocess
    )

    doc.set_item_locations()

    return doc