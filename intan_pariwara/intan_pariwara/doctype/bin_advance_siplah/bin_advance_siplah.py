# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import bold
from frappe.utils import flt
from frappe.query_builder.functions import Sum

from frappe.model.document import Document


class BinAdvanceSiplah(Document):
	
	def update_item_qty(self):
		ste = frappe.qb.DocType("Stock Entry")
		ste_item = frappe.qb.DocType("Stock Entry Detail")
		pre_order = frappe.qb.DocType("Pre Order")

		advance_siplah = (
			frappe.qb.from_(ste)
            .inner_join(ste_item)
            .on(ste.name == ste_item.parent)
			.inner_join(pre_order)
            .on(ste.pre_order == pre_order.name)
            .select(
				Sum(ste_item.qty)
            )
            .where(
                (ste.docstatus == 1) &
                (ste.stock_entry_type == "Siplah Titipan") &
				(ste.company == self.company) &
				(ste.customer == self.customer) &
				(pre_order.branch == self.branch) &
				(ste_item.t_warehouse == self.warehouse) &
				(ste_item.item_code == self.item_code)
            )
		).run()[0][0] or 0.0
		
		dn = frappe.qb.DocType("Delivery Note")
		dn_item = frappe.qb.DocType("Delivery Note Item")

		used_advance_siplah = (
			frappe.qb.from_(dn)
            .inner_join(dn_item)
            .on(dn.name == dn_item.parent)
            .select(
				Sum(dn_item.qty)
            )
            .where(
                (dn.docstatus == 1) &
                (dn.is_advance == 1) &
				(dn.company == self.company) &
				((dn.customer == self.customer) | ((dn.has_relation == 1) & (dn.relasi == self.customer))) &
				(dn.branch == self.branch) &
				(dn_item.warehouse == self.warehouse) &
				(dn_item.item_code == self.item_code)
            )
		).run()[0][0] or 0.0

		qty = flt(advance_siplah - used_advance_siplah, self.precision("qty"))
		
		if qty < 0:
			frappe.throw(f"""Customer {self.customer} of an Item {bold(self.item_code)} 
				has negative stock of quantity {bold(self.qty)} in the
                warehouse {self.warehouse}""")
			
		self.db_set("qty", qty)

def on_doctype_update():
	frappe.db.add_unique("Bin Advance Siplah", ["item_code", "customer", "branch", "warehouse"], constraint_name="unique_item_customer_wh")