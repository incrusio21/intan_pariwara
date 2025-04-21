# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.stock.get_item_details import get_bin_details
from frappe.query_builder.functions import Sum


def get_bin_item(item_code, warehouse):
    bin_actual = get_bin_details(item_code, warehouse)

    # jumlahkan dengan pick list lain sebelum packing
    mr_item = frappe.qb.DocType("Material Request Item")
    request_qty = (
        frappe.qb.from_(mr_item)
        .select(
            Sum(mr_item.qty - mr_item.ordered_qty)
        )
        .where(
            (mr_item.docstatus == 1) &
            (mr_item.from_warehouse == warehouse) &
            (mr_item.item_code == item_code)
        )
    ).run()[0][0] or 0

    bin_actual.update({"request_qty": request_qty})

    return bin_actual