# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt

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