import frappe

@frappe.whitelist()
def print_counter(doctype,docname, counter):
    frappe.db.set_value(doctype, docname, 'custom_print_counter', counter)
    frappe.db.commit()
    doc = frappe.get_doc(doctype, docname)
    return doc