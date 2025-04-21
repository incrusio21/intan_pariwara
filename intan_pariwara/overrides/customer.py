# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.selling.doctype.customer.customer import Customer
from frappe.model.naming import make_autoname, set_name_by_naming_series, set_name_from_naming_options

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
        kode_customer = ""
        if self.custom_jenis_relasi  in ["Sekolah Dikbud","Sekolah Kemenag"]:
            return
        if self.custom_jenis_relasi  in ["Guru Sekolah Dikbud","Guru Sekolah Kemenag"]:
            return
        elif self.custom_jenis_relasi  == "Instansi":
            kode_customer = self.custom_jenis_relasi[0] + self.kode_kab + self.kode_instansi + self.kode_bidangsatker + ".##"
        elif self.custom_jenis_relasi == "Desa":
            return
        elif self.custom_jenis_relasi in ["Reseller", "UMUM"]:
            kode_customer = self.custom_jenis_relasi[0] + self.kode_kab + ".####"
        
        self.custom_kode_customer = make_autoname(kode_customer, doc=self)