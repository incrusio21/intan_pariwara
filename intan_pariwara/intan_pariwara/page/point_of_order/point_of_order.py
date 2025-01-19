# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint
from frappe.utils.nestedset import get_root_of

from erpnext.accounts.doctype.pos_invoice.pos_invoice import get_stock_availability
from erpnext.accounts.doctype.pos_profile.pos_profile import get_child_nodes
from erpnext.selling.page.point_of_sale.point_of_sale import get_conditions, search_by_term

from intan_pariwara.intan_pariwara.doctype.poe_profile.poe_profile import get_item_groups

def filter_result_items(result, poe_profile):
	if result and result.get("items"):
		pos_item_groups = frappe.db.get_all("POE Item Group", {"parent": poe_profile}, pluck="item_group")
		if not pos_item_groups:
			return
		result["items"] = [item for item in result.get("items") if item.get("item_group") in pos_item_groups]
		
@frappe.whitelist()
def get_items(start, page_length, price_list, item_group, poe_profile, jenjang=None, kode_kelas=None, search_term=""):
    warehouse, hide_unavailable_items = frappe.db.get_value(
        "POE Profile", poe_profile, ["warehouse", "hide_unavailable_items"]
    )

    result = []
    # if search_term:
    #     result = search_by_term(search_term, warehouse, price_list) or []
    #     filter_result_items(result, poe_profile)
    #     if result:
    #         return result

    if not frappe.db.exists("Item Group", item_group):
        item_group = get_root_of("Item Group")

    condition = get_conditions(search_term)
    condition += get_item_group_condition(poe_profile)
    if jenjang:
        condition += """ and custom_kode_jenjang = "{}" """.format(jenjang)
    
    if kode_kelas:
        condition += """ and custom_kode_kelas = "{}" """.format(kode_kelas)

    lft, rgt = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"])

    bin_join_selection, bin_join_condition = "", ""
    if hide_unavailable_items:
        bin_join_selection = ", `tabBin` bin"
        bin_join_condition = (
            "AND bin.warehouse = %(warehouse)s AND bin.item_code = item.name AND bin.actual_qty > 0"
        )

    items_data = frappe.db.sql(
        """
        SELECT
            item.name AS item_code,
            item.item_name,
            item.description,
            item.stock_uom,
            item.image AS item_image,
            item.is_stock_item
        FROM
            `tabItem` item {bin_join_selection}
        WHERE
            item.disabled = 0
            AND item.has_variants = 0
            AND item.is_sales_item = 1
            AND item.is_fixed_asset = 0
            AND item.item_group in (SELECT name FROM `tabItem Group` WHERE lft >= {lft} AND rgt <= {rgt})
            AND {condition}
            {bin_join_condition}
        ORDER BY
            item.name asc
        LIMIT
            {page_length} offset {start}""".format(
            start=cint(start),
            page_length=cint(page_length),
            lft=cint(lft),
            rgt=cint(rgt),
            condition=condition,
            bin_join_selection=bin_join_selection,
            bin_join_condition=bin_join_condition,
        ),
        {"warehouse": warehouse},
        as_dict=1,
        debug=1
    )

    # return (empty) list if there are no results
    if not items_data:
        return result

    current_date = frappe.utils.today()

    for item in items_data:
        uoms = frappe.get_doc("Item", item.item_code).get("uoms", [])

        item.actual_qty, _ = get_stock_availability(item.item_code, warehouse)
        item.uom = item.stock_uom

        item_price = frappe.get_all(
            "Item Price",
            fields=["price_list_rate", "currency", "uom", "batch_no", "valid_from", "valid_upto"],
            filters={
                "price_list": price_list,
                "item_code": item.item_code,
                "selling": True,
                "valid_from": ["<=", current_date],
                "valid_upto": ["in", [None, "", current_date]],
            },
            order_by="valid_from desc",
            limit=1,
        )

        if not item_price:
            result.append(item)

        for price in item_price:
            uom = next(filter(lambda x: x.uom == price.uom, uoms), {})

            if price.uom != item.stock_uom and uom and uom.conversion_factor:
                item.actual_qty = item.actual_qty // uom.conversion_factor

            result.append(
                {
                    **item,
                    "price_list_rate": price.get("price_list_rate"),
                    "currency": price.get("currency"),
                    "uom": price.uom or item.uom,
                    "batch_no": price.batch_no,
                }
            )
    return {"items": result}

def get_item_group_condition(poe_profile):
	cond = "and 1=1"
	item_groups = get_item_groups(poe_profile)
	if item_groups:
		cond = "and item.item_group in (%s)" % (", ".join(["%s"] * len(item_groups)))

	return cond % tuple(item_groups)

@frappe.whitelist()
def check_opening_entry(user):
	open_vouchers = frappe.db.get_all(
		"POE Profile Session",
		filters={"user": user },
		fields=["name", "company", "poe_profile"],
	)

	return open_vouchers

@frappe.whitelist()
def create_opening_voucher(poe_profile, company):
	new_pos_opening = frappe.get_doc(
		{
			"doctype": "POE Profile Session",
			"user": frappe.session.user,
			"poe_profile": poe_profile,
			"company": company,
		}
	)
	new_pos_opening.save()

	return new_pos_opening.as_dict()

@frappe.whitelist()
def remove_opening_entry(user):
    frappe.db.sql("delete from `tabPOE Profile Session` where user = %s", (user))

    return True

@frappe.whitelist()
def get_poe_profile_data(poe_profile):
	poe_profile = frappe.get_doc("POE Profile", poe_profile)
	poe_profile = poe_profile.as_dict()

	_customer_groups_with_children = []
	for row in poe_profile.customer_groups:
		children = get_child_nodes("Customer Group", row.customer_group)
		_customer_groups_with_children.extend(children)

	poe_profile.customer_groups = _customer_groups_with_children
	return poe_profile

@frappe.whitelist()
def get_past_order_list(search_term, status, limit=20):
	fields = ["name", "grand_total", "currency", "customer", "transaction_date"]
	invoice_list = []

	if search_term and status:
		invoices_by_customer = frappe.db.get_all(
			"Pre Order",
			filters={"customer": ["like", f"%{search_term}%"], "status": status},
			fields=fields,
			page_length=limit,
		)
		invoices_by_name = frappe.db.get_all(
			"Pre Order",
			filters={"name": ["like", f"%{search_term}%"], "status": status},
			fields=fields,
			page_length=limit,
		)

		invoice_list = invoices_by_customer + invoices_by_name
	elif status:
		invoice_list = frappe.db.get_all(
			"Pre Order", filters={"status": status}, fields=fields, page_length=limit
		)

	return invoice_list