# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.stock import get_warehouse_account_map
from erpnext.accounts.general_ledger import process_gl_map, toggle_debit_credit_if_negative
from erpnext.accounts.utils import _delete_accounting_ledger_entries
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote

import intan_pariwara
from intan_pariwara.controllers.account_controller import AccountsController

class IPDeliveryNote(AccountsController, DeliveryNote):
    def validate_with_previous_doc(self):
        super(DeliveryNote, self).validate_with_previous_doc(
            {
                "Sales Order": {
                    "ref_dn_field": "against_sales_order",
                    "compare_fields": [
                        ["customer", "="],
                        ["seller", "="],
                        ["transaction_type", "="],
                        ["fund_source", "="],
                        ["company", "="],
                        ["project", "="],
                        ["currency", "="],
                    ],
                },
                "Sales Order Item": {
                    "ref_dn_field": "so_detail",
                    "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
                    "is_child_table": True,
                    "allow_duplicate_prev_row_id": True,
                },
                "Sales Invoice": {
                    "ref_dn_field": "against_sales_invoice",
                    "compare_fields": [
                        ["customer", "="],
                        ["company", "="],
                        ["project", "="],
                        ["currency", "="],
                    ],
                },
                "Sales Invoice Item": {
                    "ref_dn_field": "si_detail",
                    "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
                    "is_child_table": True,
                    "allow_duplicate_prev_row_id": True,
                },
            }
        )

        if (
            cint(frappe.db.get_single_value("Selling Settings", "maintain_same_sales_rate"))
            and not self.is_return
            and not self.is_internal_customer
        ):
            self.validate_rate_with_reference_doc(
                [
                    ["Sales Order", "against_sales_order", "so_detail"],
                    ["Sales Invoice", "against_sales_invoice", "si_detail"],
                ]
            )

    def make_gl_entries(self, gl_entries=None, from_repost=False, via_landed_cost_voucher=False):
        # ctt: jgn d push krn hanya masalah beda vesrion
        super().make_gl_entries(gl_entries, from_repost)

        # ketika hasil dari repost. ubah ledger invoice
        if from_repost and self.get("custom_use_delivery_account"):
            invoice_list = frappe.db.get_list("Sales Invoice Item", filters={"delivery_note": self.name, "docstatus": 1}, pluck="parent", group_by="parent")
            for voucher_no in invoice_list:
                voucher_obj = frappe.get_doc("Sales Invoice", voucher_no)
                expected_gle = toggle_debit_credit_if_negative(voucher_obj.get_gl_entries())
                if expected_gle:
                    _delete_accounting_ledger_entries("Sales Invoice", voucher_no)
                    voucher_obj.make_gl_entries(gl_entries=expected_gle, from_repost=True)

    def before_submit(self):
        # simpan penanda agar ketika repost bsa membedakan invoice yang harus ikut di repost dan tidak
        self.custom_use_delivery_account = intan_pariwara.is_delivery_account_enabled(self.company)

    def get_gl_entries(self, warehouse_account=None, default_expense_account=None, default_cost_center=None):
        if not warehouse_account:
            warehouse_account = get_warehouse_account_map(self.company)

        sle_map = self.get_stock_ledger_details()
        voucher_details = self.get_voucher_details(default_expense_account, default_cost_center, sle_map)

        gl_list = []
        warehouse_with_no_account = []
        precision = self.get_debit_field_precision()

        for item_row in voucher_details:
            sle_list = sle_map.get(item_row.name)
            sle_rounding_diff = 0.0
            if sle_list:
                for sle in sle_list:
                    if warehouse_account.get(sle.warehouse):
                        # from warehouse account

                        sle_rounding_diff += flt(sle.stock_value_difference)

                        if not self.custom_use_delivery_account:
                            self.check_expense_account(item_row)

                            # expense account/ target_warehouse / source_warehouse
                            if item_row.get("target_warehouse"):
                                warehouse = item_row.get("target_warehouse")
                                expense_account = warehouse_account[warehouse]["account"]
                            else:
                                expense_account = item_row.expense_account
                        else:
                            self.check_delivery_account(item_row)
                            expense_account = item_row.custom_delivery_account
                       
                        gl_list.append(
                            self.get_gl_dict(
                                {
                                    "account": warehouse_account[sle.warehouse]["account"],
                                    "against": expense_account,
                                    "cost_center": item_row.cost_center,
                                    "project": item_row.project or self.get("project"),
                                    "remarks": self.get("remarks") or _("Accounting Entry for Stock"),
                                    "debit": flt(sle.stock_value_difference, precision),
                                    "is_opening": item_row.get("is_opening")
                                    or self.get("is_opening")
                                    or "No",
                                },
                                warehouse_account[sle.warehouse]["account_currency"],
                                item=item_row,
                            )
                        )

                        gl_list.append(
                            self.get_gl_dict(
                                {
                                    "account": expense_account,
                                    "against": warehouse_account[sle.warehouse]["account"],
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
                    elif sle.warehouse not in warehouse_with_no_account:
                        warehouse_with_no_account.append(sle.warehouse)

            if abs(sle_rounding_diff) > (1.0 / (10**precision)) and self.is_internal_transfer():
                warehouse_asset_account = ""
                if self.get("is_internal_customer"):
                    warehouse_asset_account = warehouse_account[item_row.get("target_warehouse")]["account"]
                elif self.get("is_internal_supplier"):
                    warehouse_asset_account = warehouse_account[item_row.get("warehouse")]["account"]

                expense_account = frappe.get_cached_value("Company", self.company, "default_expense_account")
                if not expense_account:
                    frappe.throw(
                        _(
                            "Please set default cost of goods sold account in company {0} for booking rounding gain and loss during stock transfer"
                        ).format(frappe.bold(self.company))
                    )

                gl_list.append(
                    self.get_gl_dict(
                        {
                            "account": expense_account,
                            "against": warehouse_asset_account,
                            "cost_center": item_row.cost_center,
                            "project": item_row.project or self.get("project"),
                            "remarks": _("Rounding gain/loss Entry for Stock Transfer"),
                            "debit": sle_rounding_diff,
                            "is_opening": item_row.get("is_opening") or self.get("is_opening") or "No",
                        },
                        warehouse_account[sle.warehouse]["account_currency"],
                        item=item_row,
                    )
                )

                gl_list.append(
                    self.get_gl_dict(
                        {
                            "account": warehouse_asset_account,
                            "against": expense_account,
                            "cost_center": item_row.cost_center,
                            "remarks": _("Rounding gain/loss Entry for Stock Transfer"),
                            "credit": sle_rounding_diff,
                            "project": item_row.get("project") or self.get("project"),
                            "is_opening": item_row.get("is_opening") or self.get("is_opening") or "No",
                        },
                        item=item_row,
                    )
                )

        if warehouse_with_no_account:
            for wh in warehouse_with_no_account:
                if frappe.get_cached_value("Warehouse", wh, "company"):
                    frappe.throw(
                        _(
                            "Warehouse {0} is not linked to any account, please mention the account in the warehouse record or set default inventory account in company {1}."
                        ).format(wh, self.company)
                    )

        return process_gl_map(gl_list, precision=precision)
    
    def check_delivery_account(self, item):
        if not item.get("custom_delivery_account"):
            msg = _("Please set an Delivery Account in the Items table")
            frappe.throw(
                _("Row #{0}: Delivery Account not set for the Item {1}. {2}").format(
                    item.idx, frappe.bold(item.item_code), msg
                ),
                title=_("Delivery Account Missing"),
            )

        else:
            if not item.get("cost_center"):
                frappe.throw(
                    _("{0} {1}: Cost Center is mandatory for Item {2}").format(
                        _(self.doctype), self.name, item.get("item_code")
                    )
                )