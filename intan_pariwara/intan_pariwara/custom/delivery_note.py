# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.model.utils import get_fetch_values
from frappe.utils import cint, flt

from erpnext.stock.doctype.delivery_note.delivery_note import get_company_address, get_invoiced_qty_map, get_returned_qty_map
from erpnext.controllers.accounts_controller import merge_taxes
# from erpnext.stock.doctype.serial_no.serial_no import get_delivery_note_serial_no

def add_picking_list_to_status_updater(self, method):
	self.status_updater.extend([
		{
			"target_dt": "Packing List Item",
			"join_field": "packing_list_detail",
			"source_dt": "Delivery Note Item",
			"target_field": "delivered_qty",
			"target_parent_dt": "Packing List",
			"target_ref_field": "qty",
			"source_field": "qty",
			"percent_join_field": "against_packing_list",
			"target_parent_field": "per_delivered",
		},
	])

def add_picking_list_to_status_updater(self, method):
	self.status_updater.extend([
		{
			"target_dt": "Packing List Item",
			"join_field": "packing_list_detail",
			"source_dt": "Delivery Note Item",
			"target_field": "delivered_qty",
			"target_parent_dt": "Packing List",
			"target_ref_field": "qty",
			"source_field": "qty",
			"percent_join_field": "against_packing_list",
			"target_parent_field": "per_delivered",
		},
	])

@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None, args=None):
	doc = frappe.get_doc("Delivery Note", source_name)

	to_make_invoice_qty_map = {}
	returned_qty_map = get_returned_qty_map(source_name)
	invoiced_qty_map = get_invoiced_qty_map(source_name)

	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("set_po_nos")
		
		if len(target.get("items")) == 0:
			frappe.throw(_("All these items have already been Invoiced/Returned"))

		if args and args.get("merge_taxes"):
			merge_taxes(source.get("taxes") or [], target)
		
		target.run_method("calculate_taxes_and_totals")

		# set company address
		if source.company_address:
			target.update({"company_address": source.company_address})
		else:
			# set company address
			target.update(get_company_address(target.company))

		if target.company_address:
			target.update(get_fetch_values("Sales Invoice", "company_address", target.company_address))

	def update_item(source_doc, target_doc, source_parent):
		target_doc.qty = to_make_invoice_qty_map[source_doc.name]
		target_doc.discount_account = source_parent.rebate_account_from
		
		# if source_doc.serial_no and source_parent.per_billed > 0 and not source_parent.is_return:
		# 	target_doc.serial_no = get_delivery_note_serial_no(
		# 		source_doc.item_code, target_doc.qty, source_parent.name
		# 	)

	def get_pending_qty(item_row):
		pending_qty = item_row.qty - invoiced_qty_map.get(item_row.name, 0)

		returned_qty = 0
		if returned_qty_map.get(item_row.name, 0) > 0:
			returned_qty = flt(returned_qty_map.get(item_row.name, 0))
			returned_qty_map[item_row.name] -= pending_qty

		if returned_qty:
			if returned_qty >= pending_qty:
				pending_qty = 0
				returned_qty -= pending_qty
			else:
				pending_qty -= returned_qty
				returned_qty = 0

		to_make_invoice_qty_map[item_row.name] = pending_qty

		return pending_qty

	doc = get_mapped_doc(
		"Delivery Note",
		source_name,
		{
			"Delivery Note": {
				"doctype": "Sales Invoice",
				"field_map": {
					"payment_date": "due_date",
					"is_return": "is_return"
				},
				"validation": {"docstatus": ["=", 1]},
			},
			"Delivery Note Item": {
				"doctype": "Sales Invoice Item",
				"field_map": {
					"name": "dn_detail",
					"parent": "delivery_note",
					"so_detail": "so_detail",
					"against_sales_order": "sales_order",
					"pre_order": "against_pre_order",
					"pre_order_detail": "pre_order_detail",
					"cost_center": "cost_center",
				},
				"postprocess": update_item,
				"filter": lambda d: get_pending_qty(d) <= 0
				if not doc.get("is_return")
				else get_pending_qty(d) > 0,
			},
			"Sales Taxes and Charges": {
				"doctype": "Sales Taxes and Charges",
				"reset_value": not (args and args.get("merge_taxes")),
				"ignore": args.get("merge_taxes") if args else 0,
			},
			"Sales Team": {
				"doctype": "Sales Team",
				"field_map": {"incentives": "incentives"},
				"add_if_empty": True,
			},
		},
		target_doc,
		set_missing_values,
	)

	automatically_fetch_payment_terms = cint(
		frappe.db.get_single_value("Accounts Settings", "automatically_fetch_payment_terms")
	)
	if automatically_fetch_payment_terms:
		doc.set_payment_schedule()

	return doc