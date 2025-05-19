# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnext import get_company_currency

def execute(filters=None):
	data = []

	columns = get_columns(filters)
	entries = get_entries(filters)

	
	company_currency = get_company_currency(filters.get("company"))

	order_sales = {}
	for d in entries:
		if not (d.against_sales_order and d.seller and d.branch):
			continue
		
		key = (d.seller, d.branch)
		so_sp = order_sales.setdefault(key, {
			"qty": 0,
			"amount": 0,
			"returned_qty": 0,
			"returned_amount": 0,
			'netto': 0,
		})
		
		qty, amount = ["qty", "netto"] if d.qty > 0 else ["returned_qty", "returned_amount"] 
		so_sp[qty] += abs(d.qty)
		so_sp[amount] += abs(d.amount)
		so_sp['amount'] += abs(d.base_price_list_rate * d.qty) if d.qty > 0 else 0

	
	for (seller, branch), val in order_sales.items():
		data.append({
			"seller": seller,
			"branch": branch,
			"currency": company_currency,
		
			**val,
		})

	return columns, data

def get_entries(filters):
	conditions, values = get_conditions(filters)
	entries = frappe.db.sql(
		"""
		select
			dt.seller,
			dt_item.qty, dt_item.amount, dt_item.base_price_list_rate, dt.rounded_total, dt_item.against_sales_order,
			dt.custom_branch_delivery_note AS branch
		from
			`tabDelivery Note` dt, `tabDelivery Note Item` dt_item
		where
			dt.name = dt_item.parent
			and dt.docstatus = 1 {} order by dt.seller, branch desc
		""".format(conditions),
		tuple(values),
		as_dict=1,
		debug=1
	)

	return entries

def get_conditions(filters):
	conditions = [""]
	values = []

	for field in ["company", "seller"]:
		if filters.get(field):
			conditions.append(f"dt.{field}=%s")
			values.append(filters[field])

	if filters.get("branch"):
		conditions.append("dt.custom_branch_delivery_note = '{}'".format(filters.get("branch")))

	if filters.get("from_date"):
		conditions.append(f"dt.posting_date>=%s")
		values.append(filters["from_date"])

	if filters.get("to_date"):
		conditions.append(f"dt.posting_date<=%s")
		values.append(filters["to_date"])

	return " and ".join(conditions), values

def get_columns(filters):
	columns = [
		{
			"label": _("Seller"),
			"options": "Seller",
			"fieldname": "seller",
			"fieldtype": "Link",
			"width": 200,
		},
		{
			"label": _("Branch"),
			"options": "Branch",
			"fieldname": "branch",
			"fieldtype": "Link",
			"width": 200,
		},
		{
			"label": _("Selling Qty"), 
			"fieldname": "qty", 
			"fieldtype": "Float", 
			"width": 120
		},
		{
			"label": _("Bruto"), 
			"fieldname": "amount", 
			"options": "currency",
			"fieldtype": "Currency", 
			"width": 120
		},
		{
			"label": _("Netto"), 
			"fieldname": "netto", 
			"options": "currency",
			"fieldtype": "Currency", 
			"width": 120
		},
		{
			"label": _("Returned Qty"), 
			"fieldname": "returned_qty", 
			"fieldtype": "Float", 
			"width": 120
		},
		{
			"label": _("Returned Amount"), 
			"fieldname": "returned_amount", 
			"options": "currency",
			"fieldtype": "Currency", 
			"width": 120
		},
		# {
		# 	"label": _("Contribution %"),
		# 	"fieldname": "contribution_percentage",
		# 	"fieldtype": "Data",
		# 	"width": 110,
		# },
		# {
		# 	"label": _("Commission Rate %"),
		# 	"fieldname": "commission_rate",
		# 	"fieldtype": "Data",
		# 	"width": 100,
		# },
		# {
		# 	"label": _("Contribution Amount"),
		# 	"fieldname": "contribution_amount",
		# 	"fieldtype": "Currency",
		# 	"width": 120,
		# },
		# {"label": _("Incentives"), "fieldname": "incentives", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Currency"),
			"options": "Currency",
			"fieldname": "currency",
			"fieldtype": "Link",
			"hidden": 1,
		},
	]

	return columns
