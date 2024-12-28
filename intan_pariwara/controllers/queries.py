# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe


@frappe.whitelist()
def get_price_list_fund(
    company,
    customer,
    fund_source=None,
    rebate_from=None,
    rebate_to=None,
):
    party = frappe.get_doc("Customer", customer)
    party_details = {
        "selling_price_list": party.default_price_list or frappe.db.get_value("Selling Settings", None, "selling_price_list")
    }

    if fund_source and fund_source != party.custom_customer_fund_group:
        party_details["selling_price_list"] = frappe.get_value("Fund Source Detail", {"parent": customer, "fund_source": fund_source}, "price_list") or party_details["selling_price_list"]

    
    party_details["apply_rebate"] = frappe.get_value("Customer Fund Source", 
        party.get("custom_customer_fund_group"), "apply_rebate"
    ) if party.get("custom_customer_fund_group") else 0

    if party_details.get("apply_rebate") and not (rebate_from and rebate_to):
        if not rebate_from:
            party_details["rebate_account_from"] = frappe.get_cached_value("Company", company, "custom_rebate_order_account")

        if not rebate_to:
            party_details["rebate_account_to"] = frappe.get_cached_value("Company", company, "custom_rebate_payable_account")

    return party_details

@frappe.whitelist()
def additional_rebate_account(
    company,
    rebate_from=None,
    rebate_to=None,
):
    account_detail = {

    }
    
    if not (rebate_from and rebate_to):
        if not rebate_from:
            account_detail["rebate_account_from"] = frappe.get_cached_value("Company", company, "custom_rebate_additional_account")

        if not rebate_to:
            account_detail["rebate_account_to"] = frappe.get_cached_value("Company", company, "custom_rebate_additional_payable_account") or \
                frappe.get_cached_value("Company", company, "custom_rebate_payable_account")

    return account_detail
    