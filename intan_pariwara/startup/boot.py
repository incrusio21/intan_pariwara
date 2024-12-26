# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt"

import frappe

def bootinfo(bootinfo):
    if bootinfo.get("user") and bootinfo["user"].get("name"):
        bootinfo["user"]["update_item"] = 0
        
        roles = frappe.get_roles()

        if frappe.db.exists("Update Item Role Access", {"role": ["in", roles]}):
            bootinfo["user"]["update_item"] = 1