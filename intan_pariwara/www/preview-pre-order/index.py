# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

def get_context(context):
    app_path = frappe.local.form_dict.get("app_path")
    if not app_path:
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    context.doc = frappe.get_doc("Pre Order", app_path)
    context.relasi = frappe.get_value("Customer", context.customer, "custom_jenis_relasi")