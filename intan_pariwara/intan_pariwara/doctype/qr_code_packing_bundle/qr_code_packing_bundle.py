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
		self.get_item_detail()
		self.get_prev_doc_detail()
		if not self.kode_koli:
			self.generate_kode_koli()

		self.generate_data_qr()
		self.set_status()

	def set_status(self, db_update=False):
		reference = "Delivery Note" if self.packing_purpose == "Delivery" else "Stock Entry"

		doctype = frappe.qb.DocType(reference)

		query = (
			frappe.qb.from_(doctype)
			.select(
				doctype.name
			).where(
				(doctype.docstatus == 1)
				& (
					(doctype.qr_code == self.name) |
					(doctype.qr_code.like(self.name + "\n%")) |
					(doctype.qr_code.like("%\n" + self.name + "\n%")) |
					(doctype.qr_code.like("%\n" + self.name))
				)
			).orderby(doctype.posting_date, doctype.posting_time)
		)

		if reference == "Stock Entry":
			query = query.select(doctype.add_to_transit, doctype.outgoing_stock_entry)

		qr_code_used = query.run(as_dict=1)
		used_time, transit = 0, []
		for qr in qr_code_used:
			if qr.get("add_to_transit"):
				transit.append(qr.name)
				continue
			
			if qr.get("outgoing_stock_entry") and qr.outgoing_stock_entry not in transit:
				frappe.throw("QR code not valid. Must be generated from Stock Entry Transit {}".format(",".join(transit)))

			used_time += 1
		
		if used_time > 1 or len(transit) > 1:
			frappe.throw("QR code can only be used once")
		elif transit and not used_time:
			self.status = "Transit"
		elif qr_code_used and used_time:
			self.status = "Used"
		else:
			self.status = "Not Used"

		if db_update:
			self.db_update()

	def get_prev_doc_detail(self):
		doctype = "Sales Order"
		if self.packing_purpose == "Delivery":
			fields = ["branch", "customer_name as destination", "customer as destination_code", "relasi as dropship_to"]
		
		elif self.packing_purpose == "Material Transfer":
			fields = ["custom_branch as branch", "set_warehouse"]
			doctype = "Material Request"
		elif self.packing_purpose == "Siplah Titipan":
			fields = ["branch", "customer_name as destination", "customer as destination_code", "relasi as dropship_to"]
			doctype = "Pre Order"

		document = self.reference or (self.items[0].document_name if self.items else self.items_retail[0].document_name)
		if ref_doc := frappe.get_value(doctype, document, fields, as_dict=1):
			self.update(ref_doc)
			
			self.kab_kota = frappe.get_cached_value("Warehouse", ref_doc.set_warehouse, "custom_kab_kota") \
				if ref_doc.get("set_warehouse") else frappe.get_cached_value("Branch", ref_doc.branch, "kab_kota")
			
			self.dropship_name = frappe.get_cached_value("Customer", ref_doc.dropship_to, "customer_name") if ref_doc.get("dropship_to") else ""

	def get_item_detail(self):
		self.items = []

		doctype = frappe.qb.DocType(PACKING_TABLE[self.is_retail])
		pick_list = frappe.qb.DocType("Pick List Item")

		document_name, document_detail = "sales_order", "sales_order_item"
		if self.packing_purpose in ["Siplah Titipan", "Material Transfer"]:
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
		self.data_qr = f"{self.name}:" + ",".join(
			f"{d.document_name}:{d.item_code}:{d.get_formatted('qty')}"
			for d in self.items
		)
			
