# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import cint

def create_custom_field_for_reason(self, method=None):
    if not self.is_active:
        return
    
    frappe.clear_cache(doctype=self.document_type)
    meta = frappe.get_meta(self.document_type)
    
    if meta.get_field(self.workflow_reason_field):
        make_property_setter(
            self.document_type,
            self.workflow_reason_field,
            "hidden",
            1 - cint(self.reason_required),
            "Check",
            validate_fields_for_doctype=False,
        )

    if self.reason_required:
        create_or_update_reason_field(self, meta)

def create_or_update_reason_field(self, meta):
    if not meta.get_field(self.workflow_reason_field):
        # create custom field
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": self.document_type,
                "__islocal": 1,
                "fieldname": self.workflow_reason_field,
                "label": "Reason",
                "insert_after": self.insert_after_field,
                "read_only": 1,
                "no_copy": 1,
                "fieldtype": "Small Text",
                "owner": "Administrator",
            }
        ).save()
        
        frappe.msgprint(
            _("Created Custom Field Reason in {0}").format(self.document_type)
        )
    else:
        # update label name
        c_field = frappe.get_doc("Custom Field", {
                "dt": self.document_type,
                "fieldname": self.workflow_reason_field,
            }
        )
        
        data_update = False
        for field, val in {"label": "Reason", "insert_after": self.insert_after_field}.items():
            if c_field.get(field) != val:
                c_field.set(field, val)
                data_update = True

        if data_update:
            c_field.save()