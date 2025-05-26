# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

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
