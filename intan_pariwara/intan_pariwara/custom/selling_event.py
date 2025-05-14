# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate
from intan_pariwara.utils.data import get_bin_with_request

class SellingEvent:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        if self.method == "before_validate":
            self.validate_expected_date()
            self.update_sales_person_commision_rate()

    def validate_expected_date(self):
        if self.doc.get("is_return"):
            return
            
        date = getdate(self.doc.get("transaction_date") or self.doc.get("posting_date"))
        
        message = []
        if self.doc.meta.get_field("delivery_date") and date > getdate(self.doc.delivery_date):
            message.append("Delivery Date")
        
        if self.doc.meta.get_field("payment_date") and date > getdate(self.doc.payment_date):
            message.append("Payment Date")

        if self.doc.meta.get_field("due_date") and date > getdate(self.doc.due_date):
            message.append("Payment Date")

        if message:
            formatted_message = " and ".join([", ".join(message[:-1]), message[-1]]) if len(message) > 1 else message[0]
            frappe.throw(_("Posting date must be on or before Expected {}.".format(formatted_message)))
                        
    def update_sales_person_commision_rate(self):
        if not self.doc.meta.get_field("sales_team"):
            return

        for sp in self.doc.sales_team:
            cr = frappe.get_cached_value("Transaction Type Comission", 
                {"parent": sp.sales_person, "transaction_type": self.doc.transaction_type}, "commission_rate")
            
            if not isinstance(cr, float):
                cr = frappe.get_cached_value("Sales Person", sp.sales_person, "commission_rate")

            sp.commission_rate = cr

def validate_actual_bin(self, method):
    # skip mr purchase
    if self.doctype == "Material Request" and self.material_request_type == "Purchase":
        return

    # skip so titipan
    if self.get("delivery_before_po_siplah") == "Ya":
        return
    
    item_bin = {}
    precision = frappe.get_precision("Bin", "projected_qty")
    for d in self.items:
        if not item_bin.get(d.item_code):
            bin = get_bin_with_request(d.item_code, d.get("from_warehouse") or d.warehouse)
            detail_qty = bin.get("projected_qty", 0) - bin.get("request_qty", 0)
            item_bin.setdefault(d.item_code, {"detail_qty": detail_qty})
        
        item_bin[d.item_code]["detail_qty"] = flt(item_bin[d.item_code]["detail_qty"] - d.qty, precision)
        if item_bin[d.item_code]["detail_qty"] < 0:
            frappe.throw("Row {}: Item {} quantity exceeds warehouse projected by {}".format(d.idx, d.item_code, abs(item_bin[d.item_code]["detail_qty"])))