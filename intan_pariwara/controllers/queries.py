# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import json
import frappe
from frappe.utils.data import flt

from erpnext.stock.get_item_details import apply_price_list_on_item, get_price_list_currency_and_exchange_rate, process_args

@frappe.whitelist()
def get_price_list_fund(
    company,
    customer,
    fund_source=None,
    transaction_type=None,
):
    # get data customer
    party = frappe.get_doc("Customer", customer)
    party_details = {
        "selling_price_list": party.default_price_list or frappe.db.get_value("Selling Settings", None, "selling_price_list"),
        "is_max_rebate_applied": 0,
        "is_rebate_fixed": 0,
    }

    # simpan data fund source dan 
    fund_source = fund_source or party.get("custom_customer_fund_group")
    c_fund = frappe.get_cached_value("Customer Fund Source", fund_source, ["fund_source_type", "apply_rebate"], as_dict=1) \
        if fund_source else {}

    # cek pricelist customer berdasarkan fund source type
    if c_fund.get("fund_source_type"):
        filters = {
            "parent": customer, "fund_source_type": c_fund.fund_source_type, "parenttype": "Customer"
        }
        party_details["selling_price_list"] = frappe.get_value("Fund Source Detail", {**filters, "company": company }, "price_list") \
            or frappe.get_value("Fund Source Detail", filters, "price_list") or party_details["selling_price_list"]

    # cek customer fund source dapat apply rabat
    party_details["apply_rebate"] = c_fund.apply_rebate if c_fund else 0
    
    # cek jenis relasi
    if party.custom_jenis_relasi:
        jenis_relasi = frappe.get_value("Jenis Relasi", party.get("custom_jenis_relasi"), ["cant_have_rebate", "additional_rebate_disc"], as_dict=1)
        party_details["apply_rebate"] = 0 if jenis_relasi.cant_have_rebate else party_details["apply_rebate"]
        party_details["additional_rebate_disc"] = jenis_relasi.additional_rebate_disc or 0

    # cant_have_rebate memebuat apply rebate di non aktifkan 
    if party.custom_jenis_relasi and frappe.get_value("Jenis Relasi", party.custom_jenis_relasi, "cant_have_rebate"):
        party_details["apply_rebate"] = 0
    
    if c_fund and c_fund.fund_source_type and transaction_type == "Reguler":
        party_details.update(
            frappe.get_cached_value("Fund Source Type", c_fund.fund_source_type, ["is_max_rebate_applied", "is_rebate_fixed"], as_dict=1)
        )

    if transaction_type and fund_source:
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

@frappe.whitelist()
def apply_price_list(args, as_doc=False, doc=None):
    """Apply pricelist on a document-like dict object and return as
    {'parent': dict, 'children': list}

    :param args: See below
    :param as_doc: Updates value in the passed dict

            args = {
                    "doctype": "",
                    "name": "",
                    "items": [{"doctype": "", "name": "", "item_code": "", "brand": "", "item_group": ""}, ...],
                    "conversion_rate": 1.0,
                    "selling_price_list": None,
                    "price_list_currency": None,
                    "price_list_uom_dependant": None,
                    "plc_conversion_rate": 1.0,
                    "doctype": "",
                    "name": "",
                    "supplier": None,
                    "transaction_date": None,
                    "conversion_rate": 1.0,
                    "buying_price_list": None,
                    "ignore_pricing_rule": 0/1
            }
    """
    args = process_args(args)

    parent = get_price_list_currency_and_exchange_rate(args)
    args.update(parent)

    children = []

    if isinstance(doc, str):
        doc = json.loads(doc)
                
    if "items" in args:
        item_list = args.get("items")
        args.update(parent)

        is_max_applied = doc.get("is_max_rebate_applied")
        is_fixed = doc.get("is_rebate_fixed")
        field = "rebate" if doc.get("apply_rebate") else "discount_percentage"

        for item in item_list:
            args_copy = frappe._dict(args.copy())
            args_copy.update(item)
            # ctt: jgn d push. krn ini masalah versi erpnext
            item_details = apply_price_list_on_item(args_copy)

            if field == "rebate":
                item_details.discount_percentage = 0.0
            else:
                item_details.rebate = 0.0

            item_details.rebate_max, item_details.rebate_fix = frappe.get_cached_value("Item", args_copy.item_code, ["custom_rabat_max","custom_cb"])
            if is_fixed:
                item_details[field] = flt(item_details.get("rebate_fix")  + doc.get("additional_rebate_disc", 0))
            elif is_max_applied and item_details.get("rebate_max") and item_details.get(field, 0) > item_details.rebate_max:
                item_details.set(field, item_details.get("rebate_max"))

            children.append(item_details)
            
    if as_doc:
        args.price_list_currency = (parent.price_list_currency,)
        args.plc_conversion_rate = parent.plc_conversion_rate
        if args.get("items"):
            for i, item in enumerate(args.get("items")):
                for fieldname in children[i]:
                    # if the field exists in the original doc
                    # update the value
                    if fieldname in item and fieldname not in ("name", "doctype"):
                        item[fieldname] = children[i][fieldname]
        return args
    else:
        return {"parent": parent, "children": children}