# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.accounts.utils import get_fiscal_year

def update_plafon_promosi(self, method=None):
    if self.stock_entry_type != "Transfer of Promotional Goods":
        return
    
    current_fiscal_year = get_fiscal_year(self.posting_date, as_dict=True)
    
    promosi = frappe.get_doc("Plafon Promosi", {"fiscal_year": current_fiscal_year.name, "cabang": self.promosi_branch}, for_update=1)
    promosi.set_remaining_plafon()
