# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe


@frappe.whitelist()
def get_price_list_fund(
    customer,
    fund_source=None
):
    party = frappe.get_doc("Customer", customer)
    party_details = {
        "selling_price_list": party.default_price_list or frappe.db.get_value("Selling Settings", None, "selling_price_list")
    }

    if fund_source and fund_source != party.custom_customer_fund_group:
        party_details["selling_price_list"] = frappe.get_value("Fund Source Detail", {"parent": customer, "fund_source": fund_source}, "price_list") or party_details["selling_price_list"]

    return party_details

    