# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

def update_sales_person_commision_rate(self, method):
    if not self.meta.get_field("sales_team"):
        return
    

    for sp in self.sales_team:
        cr = frappe.get_cached_value("Transaction Type Comission", 
            {"parent": sp.sales_person, "transaction_type": self.transaction_type}, "commission_rate")
        
        if not isinstance(cr, float):
            cr = frappe.get_cached_value("Sales Person", sp.sales_person, "commission_rate")

        sp.commission_rate = cr