# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_company_address
from frappe.model.mapper import get_mapped_doc
from frappe.model.utils import get_fetch_values
from frappe.query_builder.functions import Sum
from frappe.utils import cstr, flt

from erpnext.selling.doctype.sales_order.sales_order import get_requested_item_qty
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.doctype.item.item import get_item_defaults
from erpnext.stock.get_item_details import get_bin_details, get_price_list_rate
from intan_pariwara.utils.data import get_bin_item as get_detail_bin

class SalesOrder:
	def __init__(self, doc, method):
		self.doc = doc
		self.method = method

		match self.method:
			case "before_validate":
				self.sales_person_fixed()
			case "validate":
				self.validate_produk_inti()
				self.validate_negotiation()
				self.set_pre_order_text()
			case "on_submit":
				self.create_material_request()
				self.update_preorder_percentage()
			case "on_cancel":
				self.update_preorder_percentage()

	def sales_person_fixed(self):
		if not self.doc.sales_person:
			return

		fixed_st = self.doc.get("sales_team", {"is_fixed": 1})
		# Hapus langsung fixed entries yang tidak sesuai
		for st in list(fixed_st):
			if st.sales_person != self.doc.sales_person:
				st.sales_person = self.doc.sales_person

		# Tambah entry baru jika tidak ada fixed entries yang tersisa
		if not fixed_st:
			self.doc.append("sales_team", {
				"sales_person": self.doc.sales_person,
				"allocated_percentage": 100,
				"is_fixed": 1
			})

	def validate_produk_inti(self):
		is_smart = non_smart = False
		for d in self.doc.items:
			if d.produk_inti_type == "Smartbook":
				is_smart = True
			else:
				non_smart = True

			if is_smart and non_smart:
				frappe.throw("There are Smartbook and Non-Smartbook items in a this transaction.")

	def validate_negotiation(self):
		if self.doc.get("__islocal") or self.doc.negotiations != "Yes":
			return

		item_same_rate = False
		for d in self.doc.items:
			if not d.custom_pre_order_item:
				continue

			if d.rate == frappe.get_value("Pre Order Item", d.custom_pre_order_item, "rate"):
				item_same_rate = True
				break

		if item_same_rate:
			frappe.msgprint(f"There are items with unchanged prices.")

	def set_pre_order_text(self):
		if not self.doc.preorder:
			return
		
		self.doc.pre_order_list = ", ".join([d.preorder for d in self.doc.preorder])

	def create_material_request(self):
		if self.doc.delivery_before_po_siplah == "Ya":
			return
		
		item_bin, need_item = {}, {}
		precision = frappe.get_precision("Bin", "projected_qty")

		include_w = frappe.get_all("Warehouse", filters={"include_projected_qty": 1, "is_group": 0}, pluck="name")
		
		def get_bin_item(item_code, warehouse):
			# cek bin warehouse
			bin = get_bin_details(
				item_code, warehouse, self.doc.company, True
			)

			# jumlahkan dengan stock entry dgn in_transit = 1
			ste = frappe.qb.DocType("Stock Entry")
			ste_item = frappe.qb.DocType("Stock Entry Detail")
			remaining_transit = (
				frappe.qb.from_(ste)
				.inner_join(ste_item)
				.on(ste.name == ste_item.parent)
				.select(
					Sum(ste_item.qty - ste_item.transferred_qty)
				)
				.where(
					(ste.docstatus == 1) &
					(ste.add_to_transit == 1) &
					(ste.custom_end_target == warehouse) &
					(ste.company == self.doc.company) &
					(ste_item.item_code == item_code)
				)
			).run()[0][0]

			if remaining_transit:
				bin["projected_qty"] = flt(bin["projected_qty"] + remaining_transit, precision)
				
			# jumlahkan dengan projected pada gudang yang include_projected_qty = 1 dan projected_qty > 0
			for w in include_w:
				if w == warehouse:
					continue
				
				bin_w = get_bin_details(
					item_code, w, self.doc.company, True
				)
				if bin_w["projected_qty"] > 0:
					bin["projected_qty"] = flt(bin["projected_qty"] + bin_w["projected_qty"], precision)

			return bin
		
		for d in self.doc.items:
			bin = item_bin.setdefault((d.item_code, d.warehouse), 
				get_bin_item(d.item_code, d.warehouse)
			)

			if bin["projected_qty"] < 0:
				need_item.setdefault(d.name, min(abs(bin["projected_qty"]), d.stock_qty))

			bin["projected_qty"] = flt(bin["projected_qty"] + d.stock_qty, precision)
		
		if need_item:
			mr = make_material_request(self.doc.name, needed_item=need_item)
			mr.from_so = 1
			mr.save()

			frappe.msgprint(_("Material Request {} are Created".format(mr.name)))

	def update_preorder_percentage(self):
		ordered = 100 if self.method == "on_submit" else 0
		for row in (self.doc.get("preorder") or []):
			po = frappe.get_doc("Pre Order", row.preorder)
			po.db_set("per_ordered", ordered)
			
			po.set_status()

@frappe.whitelist()
def make_material_request(source_name, target_doc=None, needed_item={}):
	requested_item_qty = get_requested_item_qty(source_name)

	def postprocess(source, target):
		target.schedule_date = source.delivery_date
		if source.tc_name and frappe.db.get_value("Terms and Conditions", source.tc_name, "buying") != 1:
			target.tc_name = None
			target.terms = None

	def get_remaining_qty(so_item):
		if needed_item:
			return needed_item.get(so_item.name, 0) or 0.0
		
		return flt(
			flt(so_item.qty)
			- flt(requested_item_qty.get(so_item.name, {}).get("qty"))
			- max(
				flt(so_item.get("delivered_qty"))
				- flt(requested_item_qty.get(so_item.name, {}).get("received_qty")),
				0,
			)
		)

	def update_item(source, target, source_parent):
		# qty is for packed items, because packed items don't have stock_qty field
		target.project = source_parent.project

		target.qty = flt(needed_item[source.name] / target.conversion_factor, target.precision("qty")) \
			if needed_item else get_remaining_qty(source)
		
		target.stock_qty = flt(target.qty) * flt(target.conversion_factor)
		target.actual_qty = get_bin_details(
			target.item_code, target.warehouse, source_parent.company, True
		).get("actual_qty", 0)

		args = target.as_dict().copy()
		args.update(
			{
				"company": source_parent.get("company"),
				"price_list": frappe.db.get_single_value("Buying Settings", "buying_price_list"),
				"currency": source_parent.get("currency"),
				"conversion_rate": source_parent.get("conversion_rate"),
			}
		)

		target.rate = flt(
			get_price_list_rate(args=args, item_doc=frappe.get_cached_doc("Item", target.item_code)).get(
				"price_list_rate"
			)
		)
		target.amount = target.qty * target.rate

	doc = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {"doctype": "Material Request", "validation": {"docstatus": ["=", 1]}},
			"Packed Item": {
				"doctype": "Material Request Item",
				"field_map": {"parent": "sales_order", "uom": "stock_uom"},
				"postprocess": update_item,
			},
			"Sales Order Item": {
				"doctype": "Material Request Item",
				"field_map": {"name": "sales_order_item", "parent": "sales_order"},
				"condition": lambda item: needed_item.get(item.name) and not frappe.db.exists(
					"Product Bundle", {"name": item.item_code, "disabled": 0}
				)
				and get_remaining_qty(item) > 0,
				"postprocess": update_item,
			},
		},
		target_doc,
		postprocess,
	)

	return doc

@frappe.whitelist()
def create_pick_list(source_name, target_doc=None):
	from erpnext.stock.doctype.packed_item.packed_item import is_product_bundle

	def validate_sales_order():
		so = frappe.get_doc("Sales Order", source_name)
		for item in so.items:
			if item.stock_reserved_qty > 0:
				frappe.throw(
					_(
						"Cannot create a pick list for Sales Order {0} because it has reserved stock. Please unreserve the stock in order to create a pick list."
					).format(frappe.bold(source_name))
				)

	def update_item_quantity(source, target, source_parent) -> None:
		picked_qty = flt(source.picked_qty) / (flt(source.conversion_factor) or 1)
		qty_to_be_picked = flt(source.qty) - max(picked_qty, flt(source.delivered_qty))

		target.qty = qty_to_be_picked
		target.stock_qty = qty_to_be_picked * flt(source.conversion_factor)
		bin_detail =  get_detail_bin(target.item_code, target.warehouse)
		target.actual_qty = bin_detail.get("actual_qty", 0)
		target.projected_qty = bin_detail.get("projected_qty", 0)
		target.reserved_qty = bin_detail.get("reserved_qty", 0)
		target.request_qty = bin_detail.get("request_qty", 0)

	def update_packed_item_qty(source, target, source_parent) -> None:
		qty = flt(source.qty)
		for item in source_parent.items:
			if source.parent_detail_docname == item.name:
				picked_qty = flt(item.picked_qty) / (flt(item.conversion_factor) or 1)
				pending_percent = (item.qty - max(picked_qty, item.delivered_qty)) / item.qty
				target.qty = target.stock_qty = qty * pending_percent
				return

	def should_pick_order_item(item) -> bool:
		return (
			abs(item.delivered_qty) < abs(item.qty)
			and item.delivered_by_supplier != 1
			and not is_product_bundle(item.item_code)
		)

	# Don't allow a Pick List to be created against a Sales Order that has reserved stock.
	validate_sales_order()

	doc = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Pick List",
				"field_map": {"set_warehouse": "parent_warehouse"},
				"validation": {"docstatus": ["=", 1]},
			},
			"Sales Order Item": {
				"doctype": "Pick List Item",
				"field_map": {"parent": "sales_order", "name": "sales_order_item"},
				"postprocess": update_item_quantity,
				"condition": should_pick_order_item,
			},
			"Packed Item": {
				"doctype": "Pick List Item",
				"field_map": {
					"parent": "sales_order",
					"name": "sales_order_item",
					"parent_detail_docname": "product_bundle_item",
				},
				"field_no_map": ["picked_qty"],
				"postprocess": update_packed_item_qty,
			},
		},
		target_doc,
	)

	doc.purpose = "Delivery"

	doc.set_item_locations()

	return doc

@frappe.whitelist()
def make_delivery_note_advance(source_name, target_doc=None, kwargs=None):
	
	def set_advance_warehouse(source, target, source_parent):		
		# Skip pricing rule when the dn is creating from the pick list
		target.ignore_pricing_rule = 1
		
		if source.delivery_before_po_siplah == "Ya":
			target.is_advance = 1
			
		advance_wh = frappe.get_cached_value("Company", target.company, "default_advance_wh")
		target.set_warehouse = advance_wh
	
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		target.run_method("set_po_nos")
		target.run_method("calculate_taxes_and_totals")
		target.run_method("set_use_serial_batch_fields")
		if source.company_address:
			target.update({"company_address": source.company_address})
		else:
			# set company address
			target.update(get_company_address(target.company))

		if target.company_address:
			target.update(get_fetch_values("Delivery Note", "company_address", target.company_address))

		# if invoked in bulk creation, validations are ignored and thus this method is nerver invoked
		if frappe.flags.bulk_transaction:
			# set target items names to ensure proper linking with packed_items
			target.set_new_name()

		customer = target.relasi if target.has_relation else target.customer
		for d in target.get("items"):
			d.warehouse = target.set_warehouse
			if qty_bin := frappe.get_value("Bin Advance Siplah", {
					"item_code": d.item_code, "customer": customer, "warehouse": d.warehouse, "branch": target.branch
				}, "qty"):
				d.qty = qty_bin if qty_bin < d.qty else d.qty

	def condition(doc):
		# make_mapped_doc sets js `args` into `frappe.flags.args`
		if frappe.flags.args and frappe.flags.args.delivery_dates:
			if cstr(doc.delivery_date) not in frappe.flags.args.delivery_dates:
				return False

		return abs(doc.delivered_qty) < abs(doc.qty) and doc.delivered_by_supplier != 1

	def update_item(source, target, source_parent):
		target.base_amount = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.base_rate)
		target.amount = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.rate)
		target.qty = flt(source.qty) - flt(source.delivered_qty)

		item = get_item_defaults(target.item_code, source_parent.company)
		item_group = get_item_group_defaults(target.item_code, source_parent.company)

		if item:
			target.cost_center = (
				frappe.db.get_value("Project", source_parent.project, "cost_center")
				or item.get("buying_cost_center")
				or item_group.get("buying_cost_center")
			)
	
	target_doc = get_mapped_doc("Sales Order", 
		source_name, 
		{
			"Sales Order": {
				"doctype": "Delivery Note", "field_map": { "payment_date": "payment_date", "custom_no_siplah": "no_siplah"},
				"validation": {"docstatus": ["=", 1]},
				"postprocess": set_advance_warehouse,
			},
			"Sales Order Item": {
				"doctype": "Delivery Note Item",
				"field_map": {
					"rate": "rate",
					"name": "so_detail",
					"parent": "against_sales_order",
					"custom_pre_order": "against_pre_order",
					"custom_pre_order_item": "pre_order_detail",
				},
				"condition": condition,
				"postprocess": update_item,
			},
			"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "reset_value": True},
			"Sales Team": {"doctype": "Sales Team", "add_if_empty": True}, 
		},
		target_doc,
		set_missing_values
	)

	return target_doc

@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, kwargs=None):
	from erpnext.stock.doctype.packed_item.packed_item import make_packing_list
	from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
		get_sre_details_for_voucher,
		get_sre_reserved_qty_details_for_voucher,
		get_ssb_bundle_for_voucher,
	)

	if not kwargs:
		kwargs = {
			"for_reserved_stock": frappe.flags.args and frappe.flags.args.for_reserved_stock,
			"skip_item_mapping": frappe.flags.args and frappe.flags.args.skip_item_mapping,
		}

	kwargs = frappe._dict(kwargs)

	sre_details = {}
	if kwargs.for_reserved_stock:
		sre_details = get_sre_reserved_qty_details_for_voucher("Sales Order", source_name)

	mapper = {
		"Sales Order": {"doctype": "Delivery Note", "field_map": { "payment_date": "payment_date", "custom_no_siplah": "no_siplah"},
		"validation": {"docstatus": ["=", 1]}},
		"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "reset_value": True},
		"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
	}

	def set_missing_values(source, target):
		if kwargs.get("ignore_pricing_rule"):
			# Skip pricing rule when the dn is creating from the pick list
			target.ignore_pricing_rule = 1

		target.run_method("set_missing_values")
		target.run_method("set_po_nos")
		target.run_method("calculate_taxes_and_totals")
		target.run_method("set_use_serial_batch_fields")
		if source.company_address:
			target.update({"company_address": source.company_address})
		else:
			# set company address
			target.update(get_company_address(target.company))

		if target.company_address:
			target.update(get_fetch_values("Delivery Note", "company_address", target.company_address))

		# if invoked in bulk creation, validations are ignored and thus this method is nerver invoked
		if frappe.flags.bulk_transaction:
			# set target items names to ensure proper linking with packed_items
			target.set_new_name()

		make_packing_list(target)

	def condition(doc):
		if doc.name in sre_details:
			del sre_details[doc.name]
			return False

		# make_mapped_doc sets js `args` into `frappe.flags.args`
		if frappe.flags.args and frappe.flags.args.delivery_dates:
			if cstr(doc.delivery_date) not in frappe.flags.args.delivery_dates:
				return False

		return abs(doc.delivered_qty) < abs(doc.qty) and doc.delivered_by_supplier != 1

	def update_item(source, target, source_parent):
		target.base_amount = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.base_rate)
		target.amount = (flt(source.qty) - flt(source.delivered_qty)) * flt(source.rate)
		target.qty = flt(source.qty) - flt(source.delivered_qty)

		item = get_item_defaults(target.item_code, source_parent.company)
		item_group = get_item_group_defaults(target.item_code, source_parent.company)

		if item:
			target.cost_center = (
				frappe.db.get_value("Project", source_parent.project, "cost_center")
				or item.get("buying_cost_center")
				or item_group.get("buying_cost_center")
			)

	if not kwargs.skip_item_mapping:
		mapper["Sales Order Item"] = {
			"doctype": "Delivery Note Item",
			"field_map": {
				"rate": "rate",
				"name": "so_detail",
				"parent": "against_sales_order",
				"custom_pre_order": "against_pre_order",
				"custom_pre_order_item": "pre_order_detail",
			},
			"condition": condition,
			"postprocess": update_item,
		}

	so = frappe.get_doc("Sales Order", source_name)
	target_doc = get_mapped_doc("Sales Order", so.name, mapper, target_doc)

	if not kwargs.skip_item_mapping and kwargs.for_reserved_stock:
		sre_list = get_sre_details_for_voucher("Sales Order", source_name)

		if sre_list:

			def update_dn_item(source, target, source_parent):
				update_item(source, target, so)

			so_items = {d.name: d for d in so.items if d.stock_reserved_qty}

			for sre in sre_list:
				if not condition(so_items[sre.voucher_detail_no]):
					continue

				dn_item = get_mapped_doc(
					"Sales Order Item",
					sre.voucher_detail_no,
					{
						"Sales Order Item": {
							"doctype": "Delivery Note Item",
							"field_map": {
								"rate": "rate",
								"name": "so_detail",
								"parent": "against_sales_order",
							},
							"postprocess": update_dn_item,
						}
					},
					ignore_permissions=True,
				)

				dn_item.qty = flt(sre.reserved_qty) * flt(dn_item.get("conversion_factor", 1))

				if sre.reservation_based_on == "Serial and Batch" and (sre.has_serial_no or sre.has_batch_no):
					dn_item.serial_and_batch_bundle = get_ssb_bundle_for_voucher(sre)

				target_doc.append("items", dn_item)
			else:
				# Correct rows index.
				for idx, item in enumerate(target_doc.items):
					item.idx = idx + 1

	# Should be called after mapping items.
	set_missing_values(so, target_doc)

	return target_doc

@frappe.whitelist()
def make_packing_list(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.purpose = "Sales Order"

		target.run_method("set_missing_values")

	doclist = get_mapped_doc(
		"Sales Order",
		source_name,
		{
			"Sales Order": {
				"doctype": "Packing List",
				"field_map": {
					"name": "doc_name",
					"letter_head": "letter_head"},
				"validation": {"docstatus": ["=", 1]},
			}
		},
		target_doc,
		set_missing_values,
	)

	return doclist
