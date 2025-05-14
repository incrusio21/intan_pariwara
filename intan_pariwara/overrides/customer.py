# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.selling.doctype.customer.customer import Customer
from frappe.model.naming import set_name_by_naming_series, set_name_from_naming_options

from intan_pariwara.intan_pariwara.doctype.customer_series.customer_series import make_autoname

class Customer(Customer):
    
    def autoname(self):
        cust_master_name = frappe.defaults.get_global_default("cust_master_name")
        if cust_master_name == "Customer Name":
            self.name = self.get_customer_name()
        elif cust_master_name == "Naming Series":
            set_name_by_naming_series(self)
        else:
            self.set_kode_customer()
            set_name_from_naming_options(frappe.get_meta(self.doctype).autoname, self)

    def set_kode_customer(self):
        if frappe.flags.in_import:
            return
        
        if kode_customer := make_autoname(self.custom_jenis_relasi, self):
            self.custom_kode_customer = kode_customer