# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt
import frappe

def validate_produk_inti_type(self, method):
    if self.custom_produk_inti:
        self.produk_inti_type = frappe.get_cached_value("Produk Inti", self.custom_produk_inti, "produk_inti_type")

    if not self.produk_inti_type:
        self.produk_inti_type = frappe.get_value("Produk Inti Type", {"is_default": 1}, "name")