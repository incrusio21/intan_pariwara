# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import json
from collections import defaultdict

import frappe
from frappe import _, _dict
from frappe.model.naming import _generate_random_string
from frappe.utils import cint, flt
from frappe.query_builder.functions import Sum, Coalesce

from frappe.model.document import Document

class PackingList(Document):
	def validate(self) -> None:
		from erpnext.utilities.transaction_base import validate_uom_is_integer

		self.validate_document()
		self.validate_case_nos()
		self.validate_items()

		validate_uom_is_integer(self, "stock_uom", "qty")
		validate_uom_is_integer(self, "weight_uom", "net_weight")

		self.set_missing_values()
		self.calculate_net_total_pkg()

		self.validate_item_not_empty()
		
	def get_pr_items_delivered_qty(self, pr_items):
		pr_items_delivered_qty = {}
		pr_items = [d.name for d in self.get("items") if d.name in pr_items]

		doctype = qty_field = None

		doctype = frappe.qb.DocType("Stock Entry Detail")
		qty_field = doctype.transfer_qty

		if doctype and qty_field:
			query = (
				frappe.qb.from_(doctype)
				.select(doctype.packing_list_item, Sum(qty_field))
				.where(
					(doctype.packing_list == self.name)
					& (doctype.packing_list_item.isin(pr_items))
					& (doctype.docstatus == 1)
				)
				.groupby(doctype.packing_list_item)
			)

			pr_items_delivered_qty = frappe._dict(query.run())

		return pr_items_delivered_qty
	
	def update_completed_qty(self, pr_items=None, update_modified=True):
		if self.purpose not in ["Material Request"]:
			return

		if not pr_items:
			pr_items = [d.name for d in self.get("items")]

		pr_items_delivered_qty = self.get_pr_items_delivered_qty(pr_items)
		for d in self.get("items"):
			if d.name in pr_items:
				d.delivered_qty = flt(pr_items_delivered_qty.get(d.name))

			frappe.db.set_value(d.doctype, d.name, "delivered_qty", d.delivered_qty)

		self._update_percent_field(
			{
				"target_dt": "Packing List Item",
				"target_parent_dt": self.doctype,
				"target_parent_field": "per_delivered",
				"target_ref_field": "delivered_qty",
				"target_field": "qty",
				"name": self.name,
			},
			update_modified,
		)

	def validate_document(self):
		"""Raises an exception if the (`Pick List`) status is not Submited"""
		
		if cint(frappe.db.get_value("Pick List", self.pick_list, "docstatus")) != 1:
			frappe.throw(
				_("A Packing List Slip can only be created for Submited Pick List.")
			)

	def validate_case_nos(self):
		"""Validate if case nos overlap. If they do, recommend next case no."""

		if cint(self.from_case_no) <= 0:
			frappe.throw(_("The 'From Package No.' field must neither be empty nor it's value less than 1."))
		elif not self.to_case_no:
			self.to_case_no = self.from_case_no
		elif cint(self.to_case_no) < cint(self.from_case_no):
			frappe.throw(_("'To Package No.' cannot be less than 'From Package No.'"))
		else:
			ps = frappe.qb.DocType("Packing List")
			res = (
				frappe.qb.from_(ps)
				.select(
					ps.name,
				)
				.where(
					(ps.pick_list == self.pick_list)
					& (ps.purpose == self.purpose)
					& (ps.docstatus == 1)
					& (
						(ps.from_case_no.between(self.from_case_no, self.to_case_no))
						| (ps.to_case_no.between(self.from_case_no, self.to_case_no))
						| ((ps.from_case_no <= self.from_case_no) & (ps.to_case_no >= self.from_case_no))
					)
				)
			)

			if res.run():
				frappe.throw(
					_("""Package No(s) already in use. Try from Package No {0}""").format(
						self.get_recommended_case_no()
					)
				)

	def validate_items(self):
		items_list = {}

		self.validasi_items_table("items", items_list)
		self.validasi_items_table("items_retail", items_list)

		for ref, item in items_list.items():
			remaining_qty = frappe.db.get_value(
				"Pick List Item",
				{"name": ref, "docstatus": 1},
				["sum(qty - packed_qty)"],
			)

			
			# item.actual_qty = frappe.get_value("Bin", {"item_code": item.item_code, "warehouse": item.warehouse}, "stock_value")			
			# if item.actual_qty < item.qty:
			# 	frappe.throw(
			# 		_("Row {0}: {1} units of {2} needed in {3} to complete this transaction..").format(
			# 			item.idx,
			# 			flt(item.qty - item.actual_qty),
			# 			item.item_code,
			# 			self.warehouse,
			# 		)
			# 	)
			if remaining_qty is None:
				frappe.throw(
					_("Please provide a valid Pick List Item reference for Item {0}.").format(
						item.item_code
					)
				)
			elif remaining_qty <= 0:
				frappe.throw(
					_("Packing List is already created for Item {0}.").format(
						frappe.bold(item.item_code)
					)
				)
			elif item.qty > remaining_qty:
				frappe.throw(
					_("Qty cannot be greater than {0} for the Item {1}.").format(
						frappe.bold(remaining_qty), frappe.bold(item.item_code)
					)
				)

	def validasi_items_table(self, table_name, items_list: dict):
		label = self.get_label_from_fieldname(table_name)
		for item in self.get(table_name):
			if item.qty <= 0:
				frappe.throw(_("Row {0} in {1}: Qty must be greater than 0.").format(item.idx, label))

			if not item.document_detail:
				frappe.throw(
					_("Row {0} in {1}: Either {2} Item reference is mandatory.").format(
						item.idx, label, self.purpose
					)
				)

			if item.meta.get_field("retail_key") and not item.get("retail_key"):
				frappe.throw(
					_("Row {0} Retail: Either Retail Key is mandatory.").format(
						item.idx
					)
				)

			items_list.setdefault(item.document_detail, _dict({"item_code": item.item_code , "qty": 0}))
			items_list[item.document_detail].qty += item.qty

	def validate_item_not_empty(self):
		if self.docstatus == 1 and not (self.get("items") or self.get("items_retail")):
			frappe.throw("Please select the item before submit")

	def set_missing_values(self):
		if not self.from_case_no:
			self.from_case_no = self.get_recommended_case_no()

		for item in self.items:
			stock_uom, weight_per_unit, weight_uom = frappe.db.get_value(
				"Item", item.item_code, ["stock_uom", "weight_per_unit", "weight_uom"]
			)

			item.stock_uom = stock_uom
			if weight_per_unit and not item.net_weight:
				item.net_weight = weight_per_unit
			if weight_uom and not item.weight_uom:
				item.weight_uom = weight_uom

	def get_recommended_case_no(self):
		"""Returns the next case no. for a new Packing List for a delivery note"""

		return (
			cint(
				frappe.db.get_value(
					"Packing List", {"pick_list": self.pick_list, "docstatus": 1}, ["max(to_case_no)"]
				)
			)
			+ 1
		)
	
	def calculate_net_total_pkg(self):
		self.net_weight_uom = self.items[0].weight_uom if self.items else None
		self.gross_weight_uom = self.net_weight_uom

		net_weight_pkg = 0
		for item in self.items:
			if item.weight_uom != self.net_weight_uom:
				frappe.throw(
					_(
						"Different UOM for items will lead to incorrect (Total) Net Weight value. Make sure that Net Weight of each item is in the same UOM."
					)
				)

			net_weight_pkg += flt(item.net_weight) * flt(item.qty)

		self.net_weight_pkg = round(net_weight_pkg, 2)

		if not flt(self.gross_weight_pkg):
			self.gross_weight_pkg = self.net_weight_pkg

	def on_submit(self):
		self.update_picklist_status()

		self.create_qr_code_items()
		self.create_qr_code_items_retail()
		
	def create_qr_code_items(self):
		for d in self.items:
			qr_code = frappe.new_doc("Qr Code Packing Bundle")
			qr_code.kode_koli = frappe.get_cached_value("Item", d.item_code, "custom_kode_koli")
			qr_code.packing_list = self.name
			qr_code.reference = self.reference
			qr_code.packing_detail= d.name
			qr_code.packing_purpose = self.purpose
			qr_code.pick_list = self.pick_list
			qr_code.save()

	def create_qr_code_items_retail(self):
		retail_key = []
		for d in self.items_retail:
			if d.retail_key in retail_key:
				continue

			qr_code = frappe.new_doc("Qr Code Packing Bundle")
			qr_code.is_retail = 1
			qr_code.packing_list = self.name
			qr_code.reference = self.reference
			qr_code.packing_detail= d.retail_key
			qr_code.packing_purpose = self.purpose
			qr_code.pick_list = self.pick_list
			qr_code.save()
			
			retail_key.append(d.retail_key)

	def on_cancel(self):
		self.update_picklist_status()
		self.remove_qr_code()
	
	def remove_qr_code(self):
		from frappe.model.delete_doc import delete_doc 

		for row in frappe.get_list("Qr Code Packing Bundle", filters={"packing_list": self.name}, pluck="name"):
			delete_doc("Qr Code Packing Bundle", row)

	def update_picklist_status(self):
		frappe.get_doc("Pick List", self.pick_list).update_packed_qty()
		
	@frappe.whitelist()
	def get_actual_qty(self):
		pass
		# for item in self.items:
		# 	if not (item.so_detail and item.item_code):
		# 		frappe.throw(
		# 			_("Row {0}: Please set Item Code and Sales Order Item.").format(
		# 				item.idx
		# 			)
		# 		)

		# 	if not item.warehouse:
		# 		frappe.throw(
		# 			_("Row {0}: Please set Warehouse.").format(
		# 				item.idx
		# 			)
		# 		)

		# 	item.actual_qty = frappe.get_value("Bin", {"item_code": item.item_code, "warehouse": item.warehouse}, "stock_value")

@frappe.whitelist()
def get_items(docname=None, purpose=None, used_item="[]"):

	if not docname:
		frappe.throw("Please Select Pick List first")

	data = json.loads(used_item)
	total_qty = defaultdict(float)
	for item in data:
		total_qty.setdefault(item['document_detail'], 0)
		total_qty[item['document_detail']] += item['qty']

	doctype = frappe.qb.DocType("Pick List Item")
	item = frappe.qb.DocType("Item")
	
	query = (
		frappe.qb.from_(doctype)
		.inner_join(item)
		.on(doctype.item_code == item.name)
		.select(
			doctype.name.as_("document_detail"),
			doctype.item_code,
			doctype.item_name,
			doctype.stock_uom,
			item.qty_per_koli,
			(doctype.qty - doctype.packed_qty).as_("remaining_qty")
		).where(
			(doctype.docstatus == 1)
			& (doctype.parent == docname)
			& (doctype.packed_qty < doctype.qty)
		).orderby(doctype.idx)
	)

	if purpose in ["Material Transfer", "Siplah Titipan"]:
		mr_item = frappe.qb.DocType("Material Request Item")
		query = (
			query.inner_join(mr_item)
			.on(doctype.material_request_item == mr_item.name)
			.select(
				doctype.material_request.as_("reference"),
				mr_item.from_warehouse,
				mr_item.warehouse
			)
		)
	elif purpose == "Delivery":
		query = (
			query.select(
				doctype.sales_order.as_("reference"),
				doctype.warehouse
			)
		)

	remaining_item = query.run(as_dict=1)
	new_remaining = []
	for d in remaining_item:
		d.remaining_qty -= total_qty.get(d.document_detail, 0)
		if d.remaining_qty > 0:
			new_remaining.append(d)

	return new_remaining

@frappe.whitelist()
def update_items(trans_items, is_retail=False):
	data = json.loads(trans_items)
	
	ress = frappe._dict({
		"package": [],
		"retail_key": "",
		"retail": [],
	})
	
	for d in data:
		# Hapus key yang tidak diperlukan sekaligus
		del d["name"], d["idx"]
		
		quantity = d["qty"]
		if d["remaining_qty"] < quantity:
			frappe.throw("Packing quantity exceeds remaining quantity.")
		
		if not cint(is_retail):
			qty_per_koli = d.get("qty_per_koli")
			if qty_per_koli:  # Jika bisa dikemas per koli
				# Hitung kemasan utuh dan sisa
				full_packs, quantity = divmod(quantity, qty_per_koli)
				# Tambahkan kemasan utuh ke package
				ress.package.extend([{**d, "qty": qty_per_koli} for _ in range(full_packs)])
			else:  # Jika tidak ada qty_per_koli
				ress.package.append(d)
				quantity = 0

		# Tambahkan sisa ke retail
		if quantity > 0:
			ress.retail.append({**d, "qty": quantity})

	if ress.retail:
		ress.retail_key = _generate_random_string(10)
	
	return ress
	
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_details(doctype, txt, searchfield, start, page_len, filters):
	from erpnext.controllers.queries import get_match_cond

	return frappe.db.sql(
		"""select name, item_name, description from `tabItem`
				where name in ( select item_code FROM `tabSales Order Item`
	 						where parent= {})
	 			and {} like "{}" {}
	 			limit  {} offset {} """.format("%s", searchfield, "%s", get_match_cond(doctype), "%s", "%s"),
		((filters or {}).get("sales_order"), "%%%s%%" % txt, page_len, start),
	)


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, kwargs=None):
	from intan_pariwara.intan_pariwara.custom.sales_order import make_delivery_note
	
	packing = frappe.get_doc("Packing List", source_name)
	
	all_table = (packing.items or []) + (packing.items_retail or [])
	so_dict = {d.reference for d in all_table}

	if not so_dict:
		frappe.throw("Packing List doesnt have reference")

	target_doc = make_delivery_note(list(so_dict)[0], kwargs={"skip_item_mapping": 1})
	# target_doc.items = []
	
	# non_packing_item = []
	# for item in target_doc.items:
	# 	packing_item = packing.get("items", {"document_detail": item.so_detail})
	# 	if packing_item:
	# 		remaining_qty = packing_item[0].qty - packing_item[0].get("delivered_qty", 0)
	# 		if item.qty > remaining_qty:
	# 			item.qty = remaining_qty

	# 		item.against_packing_list = packing.name
	# 		item.packing_list_detail = packing_item[0].name
	# 		item.warehouse = packing_item[0].warehouse
	# 	else:
	# 		non_packing_item.append(item)

	# for r in non_packing_item:
	# 	target_doc.remove(r)

	target_doc.run_method("calculate_taxes_and_totals")

	return target_doc

@frappe.whitelist()
def make_stock_entry(source_name, target_doc=None, kwargs=None):
	from erpnext.stock.doctype.material_request.material_request import make_stock_entry
	
	
	packing = frappe.get_doc("Packing List", source_name)
	
	all_table = (packing.items or []) + (packing.items_retail or [])
	mr_dict = {d.reference for d in all_table}

	if not mr_dict:
		frappe.throw("Packing List doesnt have reference")

	target_doc = make_stock_entry(list(mr_dict)[0])
	target_doc.items = []
	# non_packing_item = []
	# for item in target_doc.items:
	# 	packing_item = packing.get("items", {"document_detail": item.material_request_item})
	# 	if packing_item:
	# 		remaining_qty = packing_item[0].qty - packing_item[0].get("delivered_qty", 0)
	# 		if item.qty > remaining_qty:
	# 			item.qty = remaining_qty

	# 		item.packing_list = packing.name
	# 		item.packing_list_item = packing_item[0].name
	# 		item.s_warehouse = packing_item[0].from_warehouse
	# 		item.t_warehouse = packing_item[0].warehouse
	# 	else:
	# 		non_packing_item.append(item)

	# for r in non_packing_item:
	# 	target_doc.remove(r)
		
	return target_doc