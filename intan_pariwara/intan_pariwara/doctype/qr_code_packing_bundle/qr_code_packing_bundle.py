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
		self.set_status()

	def set_status(self, db_update=False):
		reference = "Delivery Note Item" if self.packing_purpose == "Delivery" else "Stock Entry Detail"

		doctype = frappe.qb.DocType(reference)

		query = (
			frappe.qb.from_(doctype)
			.select(
				doctype.parent
			).where(
				(doctype.docstatus == 1)
				& (
					(doctype.qr_code_no == self.name) |
					(doctype.qr_code_no.like(self.name + "\n%")) |
					(doctype.qr_code_no.like("%\n" + self.name + "\n%")) |
					(doctype.qr_code_no.like("%\n" + self.name))
				)
			)
			.groupby(doctype.parent)
			.limit(1)
		)

		if query.run():
			self.status = "Used"
		else:
			self.status = "Not Used"

		if db_update:
			self.db_update()

	def get_prev_doc_detail(self):
		if self.packing_purpose == "Delivery":
			fields = ["customer_name", "customer"]
		elif self.packing_purpose == "Material Transfer":
			fields = ["branch"]
		
		detail_doc = frappe.get_value("Pick List", self.pick_list, fields)
		self.destination, self.destination_code = detail_doc if isinstance(detail_doc, (tuple, list)) else (detail_doc, "")
	
	def get_item_detail(self):
		self.items = []

		doctype = frappe.qb.DocType(PACKING_TABLE[self.is_retail])
		pick_list = frappe.qb.DocType("Pick List Item")

		document_name, document_detail = "sales_order", "sales_order_item"
		if self.packing_purpose == "Material Transfer":
			document_name, document_detail = "material_request", "material_request_item"

		query = (
			frappe.qb.from_(doctype)
			.inner_join(pick_list)
			.on(doctype.document_detail == pick_list.name)
			.select(
				doctype.item_code,
				doctype.item_name,
				doctype.batch_no,
				doctype.description,
				doctype.qty,
				doctype.net_weight,
				doctype.stock_uom,
				doctype.weight_uom,
				doctype.from_warehouse,
				doctype.warehouse,
				pick_list[document_name].as_("document_name"),
				pick_list[document_detail].as_("document_detail")
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
			f"{d.document_name}:{d.document_detail}:{d.item_code}:{d.get_formatted('qty')}"
			for d in self.items
		)
			
