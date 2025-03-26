# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, now_datetime

from intan_pariwara.intan_pariwara.doctype.packing_list.packing_list import get_items

@frappe.whitelist()
def make_packing_list(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.run_method("set_missing_values")
		
		for d in get_items(source.name, source.purpose):
			if d.qty_per_koli:
				# Hitung kemasan utuh dan sisa
				full_packs, _ = divmod(d.remaining_qty, d.qty_per_koli)
				# Tambahkan kemasan utuh ke package
				target.extend("items", [{**d, "qty": d.qty_per_koli} for _ in range(int(full_packs))])
			else:
				target.append("items", d)

	doclist = get_mapped_doc(
		"Pick List",
		source_name,
		{
			"Pick List": {
				"doctype": "Packing List",
				"field_map": {
					"name": "pick_list",
					"custom_petugas_picking": "petugas_packing",
					"custom_nama_petugas": "nama_petugas",
					"letter_head": "letter_head"
				},
				"validation": {"docstatus": ["=", 1]},
			}
		},
		target_doc,
		set_missing_values,
	)

	return doclist

@frappe.whitelist()
def print_counter(doctype,docname, counter):
	frappe.db.set_value(doctype, docname, {
		'custom_print_counter': counter,
		'custom_last_print': now_datetime()
	})

	frappe.db.commit()
	doc = frappe.get_doc(doctype, docname)
	return doc