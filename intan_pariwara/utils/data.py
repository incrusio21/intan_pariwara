# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.query_builder.functions import Sum

def get_bin_with_request(item_code, warehouse):
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

def get_bin_details(item_code, warehouse):
	bin_details = {"projected_qty": 0, "actual_qty": 0, "reserved_qty": 0}

	if warehouse:
		from frappe.query_builder.functions import Coalesce, Sum

		bin = frappe.qb.DocType("Bin")
		bin_details = (
			frappe.qb.from_(bin)
			.select(
				Coalesce(Sum(bin.projected_qty), 0).as_("projected_qty"),
				Coalesce(Sum(bin.actual_qty), 0).as_("actual_qty"),
				Coalesce(Sum(bin.reserved_qty), 0).as_("reserved_qty"),
			)
			.where((bin.item_code == item_code) & (bin.warehouse == warehouse))
			.for_update()
		).run(as_dict=True)[0]

	return bin_details