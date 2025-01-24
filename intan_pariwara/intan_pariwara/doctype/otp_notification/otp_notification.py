# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class OTPNotification(Document):
	def validate(self):
		frappe.cache.hdel("otp_notifications", self.document_type)
