# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt
import frappe
import json
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder

from frappe.utils.data import flt
from intan_pariwara.controllers.account_controller import AccountsController
from intan_pariwara.siplah_integration.sales_order import get_transaction_details, load_siplah_items

class SalesOrder(AccountsController, SalesOrder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_updater = [
            {
                "source_dt": "Sales Order Item",
                "target_dt": "Pre Order Item",
                "join_field": "custom_pre_order_item",
                "target_field": "ordered_qty",
                "target_parent_dt": "Pre Order",
                "target_parent_field": "per_ordered",
                "target_ref_field": "qty",
                "source_field": "qty",
                "percent_join_field_parent": "pre_order",
                "status_field": "status",
				"keyword": "Ordered",
            }
        ]

    def validate(self):
        super().validate()
        if self.get("delivery_before_po_siplah") == "Ya":
            self.validate_bin_siplah()

    def set_missing_values(self, for_validate=False):
        super().set_missing_values(for_validate)
        self.set_missing_account_advance()

    def set_missing_account_advance(self):
        if self.meta.get_field("advanced_account") and not self.get("advanced_account"):
            self.set("advanced_account", frappe.get_value("Company", self.company, "selling_advance_account"))

    def update_prevdoc_status(self, flag=None):
        if self.delivery_before_po_siplah != "Ya":
            super().update_prevdoc_status(flag)

            self.update_qty()
            self.validate_qty()

    @frappe.whitelist()
    def validate_bin_siplah(self, update=False):
        error_bin_log = ""
        customer = self.relasi if self.has_relation else self.customer
        advance_wh = frappe.get_cached_value("Company", self.company, "default_advance_wh")
        for d in self.items:
            bin_qty = frappe.db.get_value("Bin Advance Siplah",
                {"item_code": d.item_code, "customer": customer, "branch": self.branch, "warehouse": advance_wh}, 
                "qty") or 0.0
            
            d.bin_siplah_qty = bin_qty
            if d.qty > bin_qty:
                error_bin_log += f"Item {d.item_code}:{d.item_name} need {flt(d.qty - bin_qty)} /n"
        
        self.error_bin_siplah = error_bin_log
        if self.error_bin_siplah:
            frappe.msgprint("There are items that have exceeded the quantity. Check error log tab for details.")
        
        if update:
            self.db_update("error_bin_siplah", error_bin_log)
            self.reload()
            
    @frappe.whitelist()
    def get_items(self):
        if self.custom_no_siplah:
            get_transaction_details(self.custom_no_siplah, json.dumps(self.siplah_json), self)

    @frappe.whitelist()
    def update_siplah_table(self):
        if self.custom_no_siplah:
            load_siplah_items(self.custom_no_siplah, self)
