# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json
from pypika import Order

import frappe
from frappe.model.utils import get_fetch_values
from frappe.query_builder.functions import IfNull

from erpnext.accounts.party import get_party_shipping_address, render_address
		
@frappe.whitelist()
def get_price_list_fund(
    company,
    customer,
    relasi=None,
    fund_source=None,
    seller=None,
    transaction_type=None,
    produk_inti=None,
):
    # Get initialize customer, fund source details, produk inti type, and transaction type
    party = frappe.get_cached_value("Customer", customer, ["default_price_list", "custom_jenis_relasi"], as_dict=1)
    c_fund = frappe.get_cached_value("Customer Fund Source", fund_source, ["fund_source_type", "apply_rebate"], as_dict=1) \
        if fund_source else {}
    produk_type = frappe.get_cached_value("Produk Inti Type", produk_inti, ["kumer", "max_rebate_disable", "fixed_rabate_disable"], as_dict=1) \
        if produk_inti else {}
    tran_type = frappe.get_cached_value("Transaction Type", transaction_type, ["fixed_price_list", "default_price_list"], as_dict=1) \
        if transaction_type else {}
    
    # Initialize base details
    party_details = {
        "selling_price_list": party.default_price_list or frappe.db.get_value("Selling Settings", None, "selling_price_list"),
        "is_max_rebate_applied": 0,
        "is_rebate_fixed": 0,
        "apply_rebate": c_fund.get("apply_rebate")
    }

    if c_fund.get("fund_source_type") and not tran_type.get("fixed_price_list"):
        party_details.update(
            frappe.get_cached_value("Fund Source Type", c_fund.fund_source_type, 
            ["is_max_rebate_applied", "is_rebate_fixed"], as_dict=1)
        )

        # Get price list
        filters = {"parent": relasi or customer, "fund_source_type": c_fund.fund_source_type, "parenttype": "Customer", "kumer": produk_type.get("kumer", 0)}
        party_details["selling_price_list"] = frappe.get_value(
            "Fund Source Detail", {**filters, "seller": seller }, "price_list") \
                or frappe.get_value("Fund Source Detail", filters, "price_list") or party_details["selling_price_list"]
    else:
        party_details["selling_price_list"] = tran_type.get("default_price_list") or party_details["selling_price_list"]

    # Produk inti overrides
    if produk_type:
        party_details.update({
            "is_max_rebate_applied": 0 if produk_type.get("max_rebate_disable") else party_details["is_max_rebate_applied"],
            "is_rebate_fixed": 0 if produk_type.get("fixed_rabate_disable") else party_details["is_rebate_fixed"]
        })

    # Check jenis relasi
    if party.custom_jenis_relasi and frappe.get_cached_value("Jenis Relasi", party.custom_jenis_relasi, "cant_have_rebate"):
        party_details["apply_rebate"] = 0
    
    # Handle rebate accounts
    company_acc = frappe.get_cached_value("Company", company, ["custom_rebate_order_account", "custom_rebate_payable_account"], as_dict=1)
    
    rebate_accounts = (frappe.get_value("Fund Source Accounts", {
        "company": company, 
        "transaction_type": transaction_type, 
        "parent": fund_source
    }, ["rebate_order_account", "rebate_payable_account"], as_dict=1) or {}) if transaction_type and fund_source else {}

    party_details.update({
        "rebate_account_from": rebate_accounts.get("rebate_order_account") or \
            company_acc.custom_rebate_order_account,
        "rebate_account_to": rebate_accounts.get("rebate_payable_account") or \
            company_acc.custom_rebate_payable_account
    })

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

@frappe.whitelist()
def get_shipping_details(doctype, relasi=None):
    party_details = frappe._dict({
        "shipping_address_name": "",
        "shipping_address": "",
    })

    if relasi:
        party_details.shipping_address_name = get_party_shipping_address(
            "Customer", relasi
        )
        
    party_details.shipping_address = render_address(
        party_details["shipping_address_name"], check_permissions=False
    )

    if doctype:
        party_details.update(
            get_fetch_values(doctype, "shipping_address_name", party_details.shipping_address_name)
        )

    return party_details

@frappe.whitelist()
def get_default_warehouse(branch, company=None):
    doc = frappe.qb.DocType("Default Warehouse")
    comp_filter = [""]

    if company:
        comp_filter.append(company)

    q = (
        frappe.qb.from_(doc)
        .select(
            doc.warehouse.as_("set_warehouse")    
        )
        .where(
            (doc.parent == branch) & 
            (IfNull(doc.company, "").isin(comp_filter))
        )
        .orderby(doc.company, order=Order.desc)
        .limit(1)
    )

    query = q.run(as_dict=True)

    return query[0] if query else {}
