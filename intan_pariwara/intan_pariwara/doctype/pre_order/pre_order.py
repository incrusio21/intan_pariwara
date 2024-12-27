# Copyright (c) 2024, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.mapper import get_mapped_doc

from erpnext.controllers.selling_controller import SellingController
from frappe.utils import flt
from frappe.utils.csvutils import getlink

class PreOrder(SellingController):
	
	def validate(self):
		super().validate()
		self.set_status()
		self.validate_uom_is_integer("stock_uom", "stock_qty")
		self.validate_uom_is_integer("uom", "qty")
		if self.items:
			self.with_items = 1

		from erpnext.stock.doctype.packed_item.packed_item import make_packing_list

		make_packing_list(self)

	def on_submit(self):
		# Check for Approving Authority
		frappe.get_doc("Authorization Control").validate_approving_authority(
			self.doctype, self.company, self.base_grand_total, self
		)

		# update enquiry status
		# self.update_opportunity("Quotation")
		# self.update_lead()

	def on_cancel(self):
		if self.lost_reasons:
			self.lost_reasons = []
		super().on_cancel()

		# update enquiry status
		self.set_status(update=True)
		# self.update_opportunity("Open")
		# self.update_lead()

@frappe.whitelist()
def make_sales_order(source_name: str, target_doc=None):
	# if not frappe.db.get_singles_value(
	# 	"Selling Settings", "allow_sales_order_creation_for_expired_quotation"
	# ):
	# 	quotation = frappe.db.get_value(
	# 		"Quotation", source_name, ["transaction_date", "valid_till"], as_dict=1
	# 	)
	# 	if quotation.valid_till and (
	# 		quotation.valid_till < quotation.transaction_date or quotation.valid_till < getdate(nowdate())
	# 	):
	# 		frappe.throw(_("Validity period of this quotation has ended."))
	sales_order_list = [] 
	for row in ["Tax", "Non Tax"]:
		doc = _make_sales_order(source_name, target_doc=None, item_type=row)
		if len(doc.items) > 0:
			doc.save()
			sales_order_list.append(doc.name)
	
	if not sales_order_list:
		frappe.throw("Can't make Sales Order")

	message = "List Sales Order :"
	for so in sales_order_list:
		message += "<br> {}".format(getlink("Sales Order", so))

	frappe.msgprint(message)

def _make_sales_order(source_name, target_doc=None, item_type="Non Tax", null_type_be="Non Tax"):
	def set_missing_values(source, target):
		if source.referral_sales_partner:
			target.sales_partner = source.referral_sales_partner
			target.commission_rate = frappe.get_value(
				"Sales Partner", source.referral_sales_partner, "commission_rate"
			)

		target.delivery_date = target.transaction_date
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(obj, target, source_parent):
		# balance_qty = obj.qty - ordered_items.get(obj.item_code, 0.0)
		# target.qty = balance_qty if balance_qty > 0 else 0
		target.stock_qty = flt(target.qty) * flt(obj.conversion_factor)

		if obj.against_blanket_order:
			target.against_blanket_order = obj.against_blanket_order
			target.blanket_order = obj.blanket_order
			target.blanket_order_rate = obj.blanket_order_rate

	def can_map_row(item) -> bool:
		"""
		Row mapping from Quotation to Sales order:
		1. If no selections, map all non-alternative rows (that sum up to the grand total)
		2. If selections: Is Alternative Item/Has Alternative Item: Map if selected and adequate qty
		3. If selections: Simple row: Map if adequate qty
		"""
		has_qty = item.qty > 0

		item_tax_type = frappe.get_cached_value("Item", item.item_code, "custom_tax_type")
		if not item_tax_type: 
			item_tax_type = null_type_be

		if item_tax_type != item_type:
			return False
		
		# if not selected_rows:
		# 	return not item.is_alternative

		# if selected_rows and (item.is_alternative or item.has_alternative_item):
		# 	return (item.name in selected_rows) and has_qty

		# Simple row
		return has_qty
	
	doclist = get_mapped_doc(
		"Pre Order",
		source_name,
		{
			"Pre Order": {
				"doctype": "Sales Order", 
				"validation": {"docstatus": ["=", 1]},
				"field_map": {"fund_source": "custom_fund_source"},
			},
			"Pre Order Item": {
				"doctype": "Sales Order Item",
				"field_map": {"parent": "custom_pre_order", "name": "custom_pre_order_item"},
				"postprocess": update_item,
				"condition": can_map_row,
			},
			"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "reset_value": True},
			"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
			"Payment Schedule": {"doctype": "Payment Schedule", "add_if_empty": True},
		},
		target_doc,
		set_missing_values,
	)

	return doclist