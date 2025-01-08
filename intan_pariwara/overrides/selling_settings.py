# Copyright (c) 2025 DAS and Contributors
# License: GNU General Public License v3. See license.txt

# For license information, please see license.txt
from frappe.utils import cint
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from erpnext.selling.doctype.selling_settings.selling_settings import SellingSettings

class SellingSettings(SellingSettings):
    
    def toggle_discount_accounting_fields(self):
        enable_discount_accounting = cint(self.enable_discount_accounting)

        for doc_type in ["Sales Invoice", "Delivery Note", "Sales Order", "Pre Order"]:
            make_property_setter(
                f"{doc_type} Item",
                "discount_account",
                "hidden",
                not (enable_discount_accounting),
                "Check",
                validate_fields_for_doctype=False,
            )
            if enable_discount_accounting:
                make_property_setter(
                    f"{doc_type} Item",
                    "discount_account",
                    "mandatory_depends_on",
                    "eval: doc.discount_amount",
                    "Code",
                    validate_fields_for_doctype=False,
                )
            else:
                make_property_setter(
                    f"{doc_type} Item",
                    "discount_account",
                    "mandatory_depends_on",
                    "",
                    "Code",
                    validate_fields_for_doctype=False,
                )

            make_property_setter(
                doc_type,
                "additional_discount_account",
                "hidden",
                not (enable_discount_accounting),
                "Check",
                validate_fields_for_doctype=False,
            )
            if enable_discount_accounting:
                make_property_setter(
                    doc_type,
                    "additional_discount_account",
                    "mandatory_depends_on",
                    "eval: doc.discount_amount",
                    "Code",
                    validate_fields_for_doctype=False,
                )
            else:
                make_property_setter(
                    doc_type,
                    "additional_discount_account",
                    "mandatory_depends_on",
                    "",
                    "Code",
                    validate_fields_for_doctype=False,
                )