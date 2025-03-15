# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from frappe.model.document import Document

PACKING_TABLE = {
	0: "Packing List Item", 
	1: "Packing List Item Retail", 
}

class QrCodePackingBundle(Document):
	def validate(self):
		self.get_prev_doc_detail()
		self.get_item_detail()
		if not self.kode_koli:
			self.generate_kode_koli()

		self.generate_data_qr()

	def get_prev_doc_detail(self):
		if self.packing_purpose == "Sales Order":
			fields = ["customer_name", "customer"]
		elif self.packing_purpose == "Sales Order":
			fields = ["custom_branch"]
		
		detail_doc = frappe.get_value(self.packing_purpose, self.packing_docname, fields)
		self.destination, self.destination_code = detail_doc if isinstance(detail_doc, (tuple, list)) else (detail_doc, "")
	
	def get_item_detail(self):
		self.items = []

		doctype = frappe.qb.DocType(PACKING_TABLE[self.is_retail])

		query = (
			frappe.qb.from_(doctype)
			.select(
				doctype.document_detail,
				doctype.item_code,
				doctype.item_name,
				doctype.batch_no,
				doctype.description,
				doctype.qty,
				doctype.net_weight,
				doctype.stock_uom,
				doctype.weight_uom,
			).where(
				(doctype.docstatus == 1)
				& (doctype.parent == self.packing_list)
			)
		)

		if self.is_retail:
			query = query.where(doctype.retail_key == self.packing_detail)
		else:
			query = query.where(doctype.name == self.packing_detail)

		total_qty = 0
		for d in query.run(as_dict=1):
			self.append("items", d)
			total_qty += d.qty

		self.total_qty = flt(total_qty, self.precision("total_qty"))

	def generate_kode_koli(self):
		if self.is_retail:
			self.kode_koli = "Koli Retail"
		else:
			self.kode_koli = frappe.get_cached_value("Item", self.items[0].item_code, "custom_kode_koli")

	def generate_data_qr(self):
		self.data_qr = ",".join(
			f"{self.packing_docname}:{d.document_detail}:{d.item_code}:{d.get_formatted('qty')}"
			for d in self.items
		)
			
