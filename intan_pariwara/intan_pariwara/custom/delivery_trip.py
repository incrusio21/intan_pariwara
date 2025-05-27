# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.desk.reportview import get_filters_cond, get_match_cond

def set_total_koli(self, method):
    self.total_koli = sum([d.jumlah_koli for d in self.delivery_stops])

def update_used_delivery_note(self, method):
    dn_list = [ds.delivery_note for ds in self.delivery_stops]

    val = 0
    if method == "on_submit":
        val = 1
        # check apakah dn sudah digunakan atau belum
        used_dn = frappe.db.get_all("Delivery Note", 
            filters={"name": ["in", dn_list], "delivery_trip_used": 1}, pluck="name")

        if used_dn:
            frappe.throw("Delivery Note {} already used".format(", ".join(used_dn)))

    frappe.db.set_value("Delivery Note", {"name": ["in", dn_list]}, "delivery_trip_used", val)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def dn_query(doctype, txt, searchfield, start, page_len, filters):
    doctype = "Delivery Note"
    
    conditions = []
    
    # tolong d ubah klo ada waktu
    return frappe.db.sql("""
            SELECT name, company, customer, set_warehouse, REPLACE(REPLACE(address_display,"<br>",""),"\n"," ") `address_display`
            FROM `tabDelivery Note`
            WHERE docstatus = 1
            and ({key} like %(txt)s) and `tabDelivery Note`.delivery_trip_used = 0
            {fcond}{mcond}
            limit %(page_len)s offset %(start)s
        """.format(
            **{
                "key": searchfield,
                "fcond": get_filters_cond(doctype, filters, conditions),
                "mcond": get_match_cond(doctype),
            }
        ),{"txt": "%%%s%%" % txt, "_txt": txt.replace("%", ""), "start": start, "page_len": page_len},as_dict=1
    )