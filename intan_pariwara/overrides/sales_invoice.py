# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.accounts.general_ledger import process_gl_map
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

from intan_pariwara.controllers.account_controller import AccountsController

class SalesInvoice(AccountsController, SalesInvoice):
    def make_item_gl_entries(self, gl_entries):
		# income account gl entries
        super().make_item_gl_entries(gl_entries)

        if not cint(self.update_stock) and self.get("custom_use_delivery_account"):
            gl_entries += self.get_gl_entries_delivery_account()

    def get_gl_entries_delivery_account(self, default_expense_account=None, default_cost_center=None):
        gl_list = []
        precision = self.get_debit_field_precision()
        
        dn_item_list = self.get_dn_item_list()
        sle_map = self.get_dn_stock_ledger_details(list(dn_item_list.keys()))
        voucher_details = self.get_voucher_details(default_expense_account, default_cost_center, sle_map)

        for item_row in voucher_details:
            dn_detail = dn_item_list.get(item_row.dn_detail)
            if not dn_detail:
                continue
            
            for item in dn_detail:
                sle_list = sle_map.get((item_row.dn_detail, item.item_code))
                if sle_list:
                    for sle in sle_list:
                        sle_value = flt((item.qty / sle.actual_qty) * sle.stock_value_difference, precision)

                        gl_list.append(
                            self.get_gl_dict(
                                {
                                    "account": item_row.custom_delivery_account,
                                    "against": item_row.expense_account,
                                    "cost_center": item_row.cost_center,
                                    "remarks": self.get("remarks") or _("Accounting Entry for Stock"),
                                    "debit": -1 * sle_value,
                                    "project": item_row.get("project") or self.get("project"),
                                    "is_opening": item_row.get("is_opening")
                                    or self.get("is_opening")
                                    or "No",
                                },
                                item=item_row,
                            )
                        )

                        gl_list.append(
                            self.get_gl_dict(
                                {
                                    "account": item_row.expense_account,
                                    "against": item_row.custom_delivery_account,
                                    "cost_center": item_row.cost_center,
                                    "project": item_row.project or self.get("project"),
                                    "remarks": self.get("remarks") or _("Accounting Entry for Stock"),
                                    "debit": sle_value,
                                    "is_opening": item_row.get("is_opening")
                                    or self.get("is_opening")
                                    or "No",
                                },
                                item=item_row,
                            )
                        )
                        
        return process_gl_map(gl_list, precision=precision) 
    
    def get_dn_item_list(self):
        il_dict = {}
        for d in self.get("items"):
            if not d.get("dn_detail"):
                frappe.throw(_("Row {0}: Doesn't have Link with Delivery Note").format(d.idx))

            dn_detail = il_dict.setdefault(d.get("dn_detail"), [])
            if self.has_product_bundle(d.item_code):
                for p in self.get("packed_items"):
                    if p.parent_detail_docname == d.name and p.parent_item == d.item_code:
                        # the packing details table's qty is already multiplied with parent's qty
                        dn_detail.append(
                            frappe._dict(
                                {
                                    "item_code": p.item_code,
                                    "name": d.name,
                                    "qty": flt(p.qty),
                                }
                            )
                        )
            else:
                dn_detail.append(
                    frappe._dict(
                        {
                            "item_code": d.item_code,
                            "name": d.name,
                            "qty": d.stock_qty,
                        }
                    )
                )

        return il_dict
    
    def get_dn_stock_ledger_details(self, voucher_detail_no):
        stock_ledger = {}
        stock_ledger_entries = frappe.db.sql(
            """
            select
                name, warehouse, stock_value_difference, valuation_rate,
                voucher_detail_no, item_code, posting_date, posting_time,
                actual_qty, qty_after_transaction
            from
                `tabStock Ledger Entry`
            where
                voucher_type="Delivery Note" and voucher_detail_no in %(detail)s and is_cancelled = 0
        """,
            {"detail": voucher_detail_no},
            as_dict=True
        )

        for sle in stock_ledger_entries:
            stock_ledger.setdefault((sle.voucher_detail_no, sle.item_code), []).append(sle)

        return stock_ledger