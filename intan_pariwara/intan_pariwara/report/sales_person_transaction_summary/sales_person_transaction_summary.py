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

	sales_person = {}
	for d in entries:
		sp = sales_person.setdefault(d.sales_person, {
			"amount": 0
		})
		
		r_d = d.rebate_rate if d.apply_rebate else d.discount_amount
		sp["amount"] += flt((d.price_list_rate - d.incoming_rate - r_d) * d.qty)
	
	for sp, val in sales_person.items():
		data.append([
			sp,
			val["amount"],
			company_currency
		])

	return columns, data

def get_entries(filters):
	conditions, values = get_conditions(filters)
	entries = frappe.db.sql(
		"""
		select
			dt.name, dt.customer, dt.territory, dt.posting_date as posting_date, dt.apply_rebate,
			dt_item.qty, dt_item.price_list_rate, dt_item.price_list_rate, dt_item.rebate_rate, dt_item.discount_amount, dt_item.incoming_rate,
			st.commission_rate, st.sales_person, st.allocated_percentage, st.allocated_amount, st.incentives
		from
			`tabDelivery Note` dt, `tabDelivery Note Item` dt_item, `tabSales Team` st
		where
			st.parent = dt.name and dt.name = dt_item.parent and st.parenttype = "Delivery Note"
			and dt.docstatus = 1 and dt.is_return != 1 {} order by st.sales_person, dt.name desc
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
			"label": _("Sales Person"),
			"options": "Sales Person",
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"width": 200,
		},
		{
			"label": _("Selling Amount"), 
			"fieldname": "amount", 
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
