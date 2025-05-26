# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate

@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.transaction_date = getdate(None)
        if getdate(source.valid_till) < target.transaction_date:
            for d in target.get("items", {"supplier_quotation": source.name}):
                d.price_list_rate = d.rate = 0

        target.run_method("set_missing_values")
        target.run_method("get_schedule_dates")
        target.run_method("calculate_taxes_and_totals")

    def update_item(obj, target, source_parent):
        target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)

    doclist = get_mapped_doc(
        "Supplier Quotation",
        source_name,
        {
            "Supplier Quotation": {
                "doctype": "Purchase Order",
                "validation": {
                    "docstatus": ["=", 1],
                },
            },
            "Supplier Quotation Item": {
                "doctype": "Purchase Order Item",
                "field_map": [
                    ["name", "supplier_quotation_item"],
                    ["parent", "supplier_quotation"],
                    ["material_request", "material_request"],
                    ["material_request_item", "material_request_item"],
                    ["sales_order", "sales_order"],
                ],
                "postprocess": update_item,
            },
            "Purchase Taxes and Charges": {
                "doctype": "Purchase Taxes and Charges",
            },
        },
        target_doc,
        set_missing_values,
    )

    return doclist