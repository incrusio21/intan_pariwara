# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

@frappe.whitelist()
def get_price_list(teritory):
    fsd = frappe.get_all("Fund Source Detail", 
        filters={"parent": teritory, "parenttype": "Territory"},
        fields=["fund_source_type", "price_list"]
    )

    return { "custom_details": fsd }