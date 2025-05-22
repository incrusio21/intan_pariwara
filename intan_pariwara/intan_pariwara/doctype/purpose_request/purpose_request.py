# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class PurposeRequest(Document):
	
	def validate(self):
		self.validate_pick_list_purpose()
		self.validate_same_purpose()
	
	def validate_pick_list_purpose(self):
		if not self.on_pick_list:
			self.pick_list_purpose = ""
		
	def validate_same_purpose(self):
		if not (self.on_material_request and self.on_pick_list):
			self.same_purpose = 0

		if self.same_purpose:
			self.pick_list_purpose = self.purpose