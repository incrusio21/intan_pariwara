# Copyright (c) 2024, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import query_builder
from frappe.model.document import Document
from frappe.query_builder.functions import Sum, Coalesce
from frappe.utils import flt

from erpnext.accounts.utils import get_fiscal_year

class PlafonPromosi(Document):
	
	def on_update(self):
		self.set_remaining_plafon()

	def set_remaining_plafon(self):
		ste = frappe.qb.DocType("Stock Entry")

		fiscal_year = get_fiscal_year(fiscal_year=self.fiscal_year, as_dict=True)
		
		conditions = (
			(ste.docstatus == 1)
			& (ste.stock_entry_type.isin(["Issue of Promotional Goods", "Receipt of Promotional Goodst"]))
			& (ste.promotion_from != "Pusat")
			& (ste.promosi_branch == self.cabang)
			& (ste.posting_date >= fiscal_year.year_start_date)
			& (ste.posting_date <= fiscal_year.year_end_date)
		)
		
		total_promotional_plafon = (
			frappe.qb.from_(ste)
			.select((Sum(ste.total_outgoing_value) - Sum(ste.total_incoming_value)).as_("amount"))
			.where(conditions)
		).run(debug=1)[0][0] or 0
	  
		remaining_plafon = flt(self.plafon_promosi - total_promotional_plafon, self.precision("remaining_plafon"))
		if remaining_plafon < 0:
			frappe.throw("Promotional Plafon limit exceeded")
		elif remaining_plafon > self.plafon_promosi:
			frappe.throw("Promotional Plafon overlimit exceeded")

		self.db_set("remaining_plafon", remaining_plafon)

def on_doctype_update():
	frappe.db.add_unique("Plafon Promosi", ["fiscal_year", "cabang"], constraint_name="unique_fiscal_branch")