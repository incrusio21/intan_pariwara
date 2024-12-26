# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.accounts.general_ledger import process_gl_map
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.controllers.selling_controller import get_serial_and_batch_bundle
from erpnext.stock.doctype.delivery_note.delivery_note import update_billed_amount_based_on_so

import intan_pariwara

class SalesInvoice(SalesInvoice):
    def update_billing_status_in_dn(self, update_modified=True):
        if self.is_return and not self.update_billed_amount_in_delivery_note:
            return
        updated_delivery_notes = []
        for d in self.get("items"):
            if d.dn_detail:
                billed_amt = frappe.db.sql(
                    """select sum(amount) from `tabSales Invoice Item`
                    where dn_detail=%s and docstatus=1""",
                    d.dn_detail,
                )
                billed_amt = billed_amt and billed_amt[0][0] or 0
                frappe.db.set_value(
                    "Delivery Note Item",
                    d.dn_detail,
                    "billed_amt",
                    billed_amt,
                    update_modified=update_modified,
                )
                updated_delivery_notes.append(d.delivery_note)
            elif d.so_detail:
                updated_delivery_notes += update_billed_amount_based_on_so(d.so_detail, update_modified)

        for dn in set(updated_delivery_notes):
            dn_doc = frappe.get_doc("Delivery Note", dn)
            dn_doc.update_billing_percentage(update_modified=update_modified)
            if self.docstatus == 1 and not self.is_return and self.get("custom_use_delivery_account") and dn_doc.per_billed < 100:
                frappe.throw(_("Invoice does not cover the entire Delivery Note #{}".format(dn)))

    def make_item_gl_entries(self, gl_entries):
		# income account gl entries
        super().make_item_gl_entries(gl_entries)

        if not cint(self.update_stock) and self.get("custom_use_delivery_account"):
            gl_entries += self.get_gl_entries_delivery_account()

    def get_gl_entries_delivery_account(self, default_expense_account=None, default_cost_center=None):
        gl_list = []
        precision = self.get_debit_field_precision()
        
        dn_item_list = self.get_dn_item_list()
        sle_map = self.get_dn_stock_ledger_details(dn_item_list)
        voucher_details = self.get_voucher_details(default_expense_account, default_cost_center, sle_map)

        for item_row in voucher_details:
            sle_list = sle_map.get(item_row.dn_detail)     
            if sle_list:
                for sle in sle_list:
                    gl_list.append(
                        self.get_gl_dict(
                            {
                                "account": item_row.custom_delivery_account,
                                "against": item_row.expense_account,
                                "cost_center": item_row.cost_center,
                                "project": item_row.project or self.get("project"),
                                "remarks": self.get("remarks") or _("Accounting Entry for Stock"),
                                "debit": flt(sle.stock_value_difference, precision),
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
                                "remarks": self.get("remarks") or _("Accounting Entry for Stock"),
                                "debit": -1 * flt(sle.stock_value_difference, precision),
                                "project": item_row.get("project") or self.get("project"),
                                "is_opening": item_row.get("is_opening")
                                or self.get("is_opening")
                                or "No",
                            },
                            item=item_row,
                        )
                    )
                    
        return process_gl_map(gl_list, precision=precision) 
    
    def get_dn_item_list(self):
        il, dn_il = [], set()
        for d in self.get("items"):
            if not d.get("dn_detail"):
                frappe.throw(_("Row {0}: Doesn't have Link with Delivery Note").format(d.idx))

            if self.has_product_bundle(d.item_code):
                for p in self.get("packed_items"):
                    if p.parent_detail_docname == d.name and p.parent_item == d.item_code:
                        # the packing details table's qty is already multiplied with parent's qty
                        il.append(
                            frappe._dict(
                                {
                                    "item_code": p.item_code,
                                    "qty": flt(p.qty),
                                    "dn_detail": d.get("dn_detail"),
                                }
                            )
                        )
            else:
                il.append(
                    frappe._dict(
                        {
                            "item_code": d.item_code,
                            "qty": d.stock_qty,
                            "dn_detail": d.get("dn_detail"),
                        }
                    )
                )

            dn_il.add(d.dn_detail)

        return dn_il
    
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
                voucher_type="Delivery Note" and voucher_detail_no in (%(detail)s) and is_cancelled = 0
        """,
            {"detail": voucher_detail_no},
            as_dict=True,
            debug=1
        )

        for sle in stock_ledger_entries:
            stock_ledger.setdefault(sle.voucher_detail_no, []).append(sle)

        return stock_ledger