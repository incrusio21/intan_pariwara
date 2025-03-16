# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns(filters)

	res = get_result(filters)

	return columns, res

def get_result(filters):
	unit_sold = frappe.db.sql(
		f"""
		select
			dni.item_code, dni.item_name, dni.item_group, dni.qty, dni.stock_qty, dni.price_list_rate, dni.amount,
			i.group
		from `tabDelivery Note Item` dni
		join `tabItem` i on i.name = dni.item_code
		join `tabDelivery Note` dn on dni.parent = dn.name
		where dn.docstatus = 1 and company=%(company)s {get_conditions(filters)}
	""",
		filters,
		as_dict=1
	)

	item_sold = {}
	for d in unit_sold:
		item = item_sold.setdefault(d.item_code, { 
			"item_code": d.item_code, 
			"item_name": d.item_name, 
			"item_group": d.item_group, 
			"principal": d.group, 
			"qty": 0, 
			"bruto": 0.0, 
			"netto": 0.0, 
		})

		item["qty"] += d.stock_qty
		item["bruto"] += flt(d.qty * d.price_list_rate)
		item["netto"] += d.amount
	
	return sorted(
		list(item_sold.values()), key=lambda x: x['qty'], reverse=True) \
		or []

def get_conditions(filters):
	conditions = []

	if filters.get("item_group"):
		conditions.append("item_group = %(item_group)s")
	
	conditions.append("(posting_date between %(from_date)s and %(to_date)s)")

	return "and {}".format(" and ".join(conditions)) if conditions else ""

def get_columns(filters):
	columns = [
		{
			"label": _("Item"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 100,
		},
		{"label": _("Item Name"), "fieldname": "item_name", "width": 150},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"hidden": filters.get("item_group"),
			"width": 100,
		},
		{
			"label": _("Principal"),
			"fieldname": "principal",
			"fieldtype": "Link",
			"options": "Company",
			"width": 100,
		},
		{
			"label": _("Units Sold"),
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Bruto Value"),
			"fieldname": "bruto",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Netto Value"),
			"fieldname": "netto",
			"fieldtype": "Float",
			"width": 130,
		},
	]

	return columns