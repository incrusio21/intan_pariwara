# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from frappe.model.document import Document
from frappe.utils import flt

from erpnext.controllers.status_updater import StatusUpdater

class SalesReturnRequest(StatusUpdater):
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.status_updater = [
			{
				"source_dt": "Sales Return Request Item",
				"target_dt": "Delivery Note Item",
				"target_parent_dt": "Delivery Note",
				"target_field": "return_request_qty",
				"target_ref_field": "qty",
				"source_field": "qty",
				"target_parent_field": "per_return_request",
				"percent_join_field_parent": "delivery_note",
				"join_field": "dn_detail",
			}
		]

	def validate(self) -> None:
		from erpnext.utilities.transaction_base import validate_uom_is_integer

		self.validate_items()

		validate_uom_is_integer(self, "stock_uom", "qty")
		validate_uom_is_integer(self, "weight_uom", "net_weight")

		self.set_missing_values()
		self.set_customer_mobile_no()

	def on_submit(self):
		self.update_prevdoc_status()

	def on_cancel(self):
		self.update_prevdoc_status()

	def set_customer_mobile_no(self):
		if self.contact_person:
			return
		
		self.contact_mobile = frappe.get_cached_value("Customer", self.customer, "mobile_no")

	def validate_items(self):
		for item in self.items:
			if item.qty <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than 0.").format(item.idx))

			if not item.dn_detail:
				frappe.throw(
					_("Row {0}: Either Delivery Note Item reference is mandatory.").format(
						item.idx
					)
				)

			remaining_qty = frappe.db.get_value(
				"Delivery Note Item",
				{"name": item.dn_detail, "docstatus": 1},
				["sum(stock_qty - return_request_qty)"],
			)

			if remaining_qty is None:
				frappe.throw(
					_("Row {0}: Please provide a valid Delivery Note Item reference.").format(
						item.idx,
					)
				)
			elif remaining_qty <= 0:
				frappe.throw(
					_("Row {0}: Sales Return Request is already created for Item {1}.").format(
						item.idx, frappe.bold(item.item_code)
					)
				)
			elif item.qty > remaining_qty:
				frappe.throw(
					_("Row {0}: Qty cannot be greater than {1} for the Item {2}.").format(
						item.idx, frappe.bold(remaining_qty), frappe.bold(item.item_code)
					)
				)

	def set_missing_values(self):
		self.set_missing_item_detail()
		self.set_missing_lead_customer_details()

	def set_missing_item_detail(self):
		total_qty = 0
		for item in self.items:
			stock_uom, weight_per_unit, weight_uom = frappe.db.get_value(
				"Item", item.item_code, ["stock_uom", "weight_per_unit", "weight_uom"]
			)

			item.stock_uom = stock_uom
			if weight_per_unit and not item.net_weight:
				item.net_weight = weight_per_unit
			if weight_uom and not item.weight_uom:
				item.weight_uom = weight_uom

			total_qty += item.qty
			
		self.total_qty = flt(total_qty, self.precision("total_qty"))

	def set_missing_lead_customer_details(self):
		from erpnext.accounts.party import get_default_contact

		self.contact_person = get_default_contact("Customer", self.customer)

		if not self.contact_person:
			self.update(
				{
					"contact_person": None,
					"contact_display": None,
					"contact_email": None,
					"contact_mobile": None,
					"contact_phone": None,
					"contact_designation": None,
					"contact_department": None,
				}
			)
		else:
			fields = [
				"name as contact_person",
				"full_name as contact_display",
				"email_id as contact_email",
				"mobile_no as contact_mobile",
				"phone as contact_phone",
				"designation as contact_designation",
				"department as contact_department",
			]

			contact_details = frappe.db.get_value("Contact", self.contact_person, fields, as_dict=True)

			self.update(contact_details)

@frappe.whitelist()
def make_sales_return(source_name, target_doc=None):
	from erpnext.controllers.sales_and_purchase_return import make_return_doc

	return_request = frappe.get_doc("Sales Return Request", source_name)

	target_doc = make_return_doc("Delivery Note", return_request.delivery_note, target_doc)

	non_request_item = []
	for item in target_doc.items:
		request_item = return_request.get("items", {"dn_detail": item.dn_detail})
		if request_item:
			remaining_qty = request_item[0].qty - request_item[0].get("received_qty", 0)
			if abs(item.qty) > remaining_qty:
				item.qty = -1 * remaining_qty

			item.against_srr = return_request.name
			item.srr_detail = request_item[0].name
			item.warehouse = request_item[0].warehouse
		
		if not request_item or not item.qty:
			non_request_item.append(item)

	for r in non_request_item:
		target_doc.remove(r)			

	return target_doc