# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _, scrub
from frappe.utils import cint, flt
from frappe.query_builder.functions import Sum

from erpnext.controllers.status_updater import StatusUpdater

class PackingList(StatusUpdater):
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		purpose_dict = {
			"target_dt": "Sales Order Item",
			"target_parent_dt": "Sales Order",
		}

		if self.purpose == "Material Request": 
			purpose_dict = {
				"target_dt": "Material Request Item",
				"target_parent_dt": "Material Request",
			}

		self.status_updater = [
			{
				"target_field": "packed_qty",
				"target_ref_field": "qty",
				"source_dt": "Packing List Item",
				"source_field": "qty",
				"target_parent_field": "per_packing",
				"percent_join_field_parent": "doc_name",
				"join_field": "document_detail",
				**purpose_dict,
				
			}
		]

	def validate(self) -> None:
		from erpnext.utilities.transaction_base import validate_uom_is_integer

		self.validate_document()
		self.validate_case_nos()
		self.validate_items()

		validate_uom_is_integer(self, "stock_uom", "qty")
		validate_uom_is_integer(self, "weight_uom", "net_weight")

		self.set_missing_values()
		self.calculate_net_total_pkg()

	def on_submit(self):
		self.update_prevdoc_status()

	def on_cancel(self):
		self.update_prevdoc_status()

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
		"""Raises an exception if the (`Sales Order`, `Material Request`) status is not Submited"""
		
		if cint(frappe.db.get_value(self.purpose, self.doc_name, "docstatus")) != 1:
			frappe.throw(
				_("A Packing List Slip can only be created for Submited {}.").format(self.purpose)
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
					(ps.doc_name == self.doc_name)
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
		for item in self.items:
			if item.qty <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than 0.").format(item.idx))

			if not item.document_detail:
				frappe.throw(
					_("Row {0}: Either {1} Item reference is mandatory.").format(
						item.idx, self.purpose
					)
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

			remaining_qty = frappe.db.get_value(
				f"{self.purpose} Item",
				{"name": item.document_detail, "docstatus": 1},
				["sum(qty - packed_qty)"],
			)

			if remaining_qty is None:
				frappe.throw(
					_("Row {0}: Please provide a valid {1} Item reference.").format(
						item.idx,
						self.purpose
					)
				)
			elif remaining_qty <= 0:
				frappe.throw(
					_("Row {0}: Packing List is already created for Item {1}.").format(
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
					"Packing List", {"doc_name": self.doc_name, "docstatus": 1}, ["max(to_case_no)"]
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
	
	target_doc = make_delivery_note(packing.doc_name)
	non_packing_item = []
	for item in target_doc.items:
		packing_item = packing.get("items", {"document_detail": item.so_detail})
		if packing_item:
			remaining_qty = packing_item[0].qty - packing_item[0].get("delivered_qty", 0)
			if item.qty > remaining_qty:
				item.qty = remaining_qty

			item.against_packing_list = packing.name
			item.packing_list_detail = packing_item[0].name
			item.warehouse = packing_item[0].warehouse
		else:
			non_packing_item.append(item)

	for r in non_packing_item:
		target_doc.remove(r)

	target_doc.run_method("calculate_taxes_and_totals")

	return target_doc

@frappe.whitelist()
def make_stock_entry(source_name, target_doc=None, kwargs=None):
	from erpnext.stock.doctype.material_request.material_request import make_stock_entry
	
	
	packing = frappe.get_doc("Packing List", source_name)
	
	target_doc = make_stock_entry(packing.doc_name)
	non_packing_item = []
	for item in target_doc.items:
		packing_item = packing.get("items", {"document_detail": item.material_request_item})
		if packing_item:
			remaining_qty = packing_item[0].qty - packing_item[0].get("delivered_qty", 0)
			if item.qty > remaining_qty:
				item.qty = remaining_qty

			item.packing_list = packing.name
			item.packing_list_item = packing_item[0].name
			item.s_warehouse = packing_item[0].from_warehouse
			item.t_warehouse = packing_item[0].warehouse
		else:
			non_packing_item.append(item)

	for r in non_packing_item:
		target_doc.remove(r)
		
	return target_doc