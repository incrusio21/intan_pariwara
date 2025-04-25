# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt

def set_annual_revenue_potensi(self, method):
    self.annual_revenue_potensi_bos = flt(self.annual_revenue_dana_bos * self._annual_revenue_dana_bos / 100)
    self.total_annual_revenue_potensi = flt(self.annual_revenue_potensi_dana_siswa + self.annual_revenue_potensi_bos)