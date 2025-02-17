# Copyright (c) 2024, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import query_builder
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import flt


class PlafonPromosi(Document):
	
	def on_update(self):
		self.set_remaining_plafon()

	def set_remaining_plafon(self):
		ste = frappe.qb.DocType("Stock Entry")

		year = query_builder.CustomFunction("YEAR", ["date"])

		conditions = (
			(ste.docstatus == 1)
			& (ste.stock_entry_type == "Transfer of Promotional Goods")
			& (ste.branch == self.cabang)
			& (year(ste.posting_date) == self.fiscal_year)
		)
		
		total_promotional_plafon = (
			frappe.qb.from_(ste)
			.select(Sum(ste.total_incoming_value).as_("amount"))
			.where(conditions)
		).run(as_dict=True)[0]
		
		remaining_plafon = flt(self.plafon_promosi - (total_promotional_plafon.amount or 0.0), self.precision("remaining_plafon"))
		if remaining_plafon < 0:
			frappe.throw("Promotional Plafon limit exceeded")

		self.db_set("remaining_plafon", remaining_plafon)

def on_doctype_update():
	frappe.db.add_unique("Plafon Promosi", ["fiscal_year", "cabang"], constraint_name="unique_fiscal_branch")