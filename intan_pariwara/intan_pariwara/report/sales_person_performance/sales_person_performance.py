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
		if not (d.against_sales_order and d.sales_person):
			continue
		
		key = (d.against_sales_order, d.sales_person)
		so_sp = order_sales.setdefault(key, {
			"customer": d.customer,
			"qty": 0,
			"amount": 0,
			"returned_qty": 0,
			"returned_amount": 0
		})
		
		qty, amount = ["qty", "amount"] if d.qty > 0 else ["returned_qty", "returned_amount"] 
		so_sp[qty] += abs(d.qty)
		so_sp[amount] += abs(d.amount)
	
	for (sales_order, sales_person), val in order_sales.items():
		data.append({
			"sales_order": sales_order,
			"sales_person": sales_person,
			"currency": company_currency,
			**val,
		})

	return columns, data

def get_entries(filters):
	conditions, values = get_conditions(filters)
	entries = frappe.db.sql(
		"""
		select
			dt.name, dt.customer, dt.territory, dt.posting_date as posting_date,
			dt_item.qty, dt_item.amount, dt_item.against_sales_order,
			st.sales_person
		from
			`tabDelivery Note` dt, `tabDelivery Note Item` dt_item, `tabSales Team` st
		where
			st.parent = dt.name and dt.name = dt_item.parent and st.parenttype = "Delivery Note"
			and dt.docstatus = 1 {} order by st.sales_person, dt.name desc
		""".format(conditions),
		tuple(values),
		as_dict=1,
	)

	return entries

def get_conditions(filters):
	conditions = [""]
	values = []

	for field in ["company", "customer", "territory"]:
		if filters.get(field):
			conditions.append(f"dt.{field}=%s")
			values.append(filters[field])

	if filters.get("sales_person"):
		conditions.append("st.sales_person = '{}'".format(filters.get("sales_person")))

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
			"label": _("Sales Order"),
			"options": "Sales Order",
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"width": 140,
		},
		{
			"label": _("Customer"),
			"options": "Customer",
			"fieldname": "customer",
			"fieldtype": "Link",
			"width": 140,
		},
		{
			"label": _("Sales Person"),
			"options": "Sales Person",
			"fieldname": "sales_person",
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
			"label": _("Selling Amount"), 
			"fieldname": "amount", 
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
