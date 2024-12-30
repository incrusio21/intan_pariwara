# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe


@frappe.whitelist()
def get_price_list_fund(
    company,
    customer,
    fund_source=None,
    transaction_type=None,
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

    if party_details.get("apply_rebate"):
        if transaction_type:
            r_account = frappe.get_value("Fund Source Accounts", 
                {"company": company, "transaction_type": transaction_type, "parent": fund_source}, ["rebate_order_account", "rebate_payable_account"], as_dict=1)
            
            if r_account:
                party_details.update({
                    "rebate_account_from": r_account.rebate_order_account,
                    "rebate_account_to": r_account.rebate_payable_account,
                })

        if not party_details.get("rebate_account_from"):
            party_details["rebate_account_from"] = frappe.get_cached_value("Company", company, "custom_rebate_order_account")

        if not party_details.get("rebate_account_to"):
            party_details["rebate_account_to"] = frappe.get_cached_value("Company", company, "custom_rebate_payable_account")

    return party_details

@frappe.whitelist()
def additional_rebate_account(
    company,
    fund_source=None,
    transaction_type=None,
):
    account_detail = {}
    if transaction_type:
        r_account = frappe.get_value("Fund Source Accounts", 
            {"company": company, "transaction_type": transaction_type, "parent": fund_source}, [
                "rebate_additional_account", "rebate_payable_account", "rebate_additional_payable_account"], as_dict=1)
        
        if r_account:
            account_detail.update({
                "rebate_account_from": r_account.rebate_order_account,
                "rebate_account_to": r_account.rebate_additional_payable_account or r_account.rebate_payable_account,
            })

    if not account_detail.get("rebate_account_from"):
        account_detail["rebate_account_from"] = frappe.get_cached_value("Company", company, "custom_rebate_additional_account")

    if not account_detail.get("rebate_account_to"):
        account_detail["rebate_account_to"] = frappe.get_cached_value("Company", company, "custom_rebate_additional_payable_account") or \
            frappe.get_cached_value("Company", company, "custom_rebate_payable_account")

    return account_detail
    