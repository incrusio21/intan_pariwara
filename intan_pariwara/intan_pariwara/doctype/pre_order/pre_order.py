# Copyright (c) 2024, DAS and contributors
# For license information, please see license.txt

import frappe

from erpnext.controllers.selling_controller import SellingController

class PreOrder(SellingController):
	
	def validate(self):
		super().validate()
		self.set_status()
		self.validate_uom_is_integer("stock_uom", "stock_qty")
		self.validate_uom_is_integer("uom", "qty")
		self.set_customer_name()
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

	def set_customer_name(self):
		if self.party_name and self.quotation_to == "Customer":
			self.customer_name = frappe.db.get_value("Customer", self.party_name, "customer_name")
		elif self.party_name and self.quotation_to == "Lead":
			lead_name, company_name = frappe.db.get_value(
				"Lead", self.party_name, ["lead_name", "company_name"]
			)
			self.customer_name = company_name or lead_name
		elif self.party_name and self.quotation_to == "Prospect":
			self.customer_name = self.party_name
		elif self.party_name and self.quotation_to == "CRM Deal":
			self.customer_name = frappe.db.get_value("CRM Deal", self.party_name, "organization")