# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.modules import scrub
from frappe.utils import flt
from frappe.model.document import Document

from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals, get_round_off_applicable_accounts
class calculate_taxes_and_totals(calculate_taxes_and_totals):
    def __init__(self, doc: Document):
        self.doc = doc
        frappe.flags.round_off_applicable_accounts = []
        frappe.flags.round_row_wise_tax = frappe.db.get_single_value(
            "Accounts Settings", "round_row_wise_tax"
        )
        
        self._items = self.filter_rows() if self.doc.doctype == "Quotation" else self.doc.get("items")

        get_round_off_applicable_accounts(self.doc.company, frappe.flags.round_off_applicable_accounts)
        self.calculate()

    def initialize_taxes(self):
        # tambahkan tax template jika tidak ada satupun tax
        if not self.doc.taxes:
            self.doc.append_taxes_from_item_tax_template()

        super().initialize_taxes()
               
    def set_discount_amount(self):
        if self.doc.customer[0] == "R" and \
            self.doc.custom_calon_siplah == "Ya":

            self.doc.discount_amount = frappe.get_cached_value("Company", self.doc.company, "default_siplah_discount") \
                if not self.already_discount else 0.0
                
        if self.doc.additional_discount_percentage:
            self.doc.discount_amount = flt(
                flt(self.doc.get(scrub(self.doc.apply_discount_on)))
                * self.doc.additional_discount_percentage
                / 100,
                self.doc.precision("discount_amount"),
            )

    # update agar doctype pre order dianggap bagian dari penjualan
    def calculate_totals(self):
        if self.doc.get("taxes"):
            self.doc.grand_total = flt(self.doc.get("taxes")[-1].total) + flt(
                self.doc.get("grand_total_diff")
            )
        else:
            self.doc.grand_total = flt(self.doc.net_total)

        if self.doc.get("taxes"):
            self.doc.total_taxes_and_charges = flt(
                self.doc.grand_total - self.doc.net_total - flt(self.doc.get("grand_total_diff")),
                self.doc.precision("total_taxes_and_charges"),
            )
        else:
            self.doc.total_taxes_and_charges = 0.0

        self._set_in_company_currency(self.doc, ["total_taxes_and_charges", "rounding_adjustment"])

        if self.doc.doctype in [
            "Pre Order",
            "Quotation",
            "Sales Order",
            "Delivery Note",
            "Sales Invoice",
            "POS Invoice",
        ]:
            self.doc.base_grand_total = (
                flt(self.doc.grand_total * self.doc.conversion_rate, self.doc.precision("base_grand_total"))
                if self.doc.total_taxes_and_charges
                else self.doc.base_net_total
            )
        else:
            self.doc.taxes_and_charges_added = self.doc.taxes_and_charges_deducted = 0.0
            for tax in self.doc.get("taxes"):
                if tax.category in ["Valuation and Total", "Total"]:
                    if tax.add_deduct_tax == "Add":
                        self.doc.taxes_and_charges_added += flt(tax.tax_amount_after_discount_amount)
                    else:
                        self.doc.taxes_and_charges_deducted += flt(tax.tax_amount_after_discount_amount)

            self.doc.round_floats_in(self.doc, ["taxes_and_charges_added", "taxes_and_charges_deducted"])

            self.doc.base_grand_total = (
                flt(self.doc.grand_total * self.doc.conversion_rate)
                if (self.doc.taxes_and_charges_added or self.doc.taxes_and_charges_deducted)
                else self.doc.base_net_total
            )

            self._set_in_company_currency(self.doc, ["taxes_and_charges_added", "taxes_and_charges_deducted"])

        self.doc.round_floats_in(self.doc, ["grand_total", "base_grand_total"])

        self.set_rounded_total()

    # update agar dapat menghitung nilai rabat
    def calculate_item_values(self):
        if self.doc.get("is_consolidated"):
            return

        if not self.discount_amount_applied:
            field = "rebate" if self.doc.get("apply_rebate") else "discount_percentage"
            apply_rebate = self.doc.get("apply_rebate")
            is_max_applied = self.doc.get("is_max_rebate_applied")
            is_fixed = self.doc.get("is_rebate_fixed")
            add_rebate_disc = self.doc.get("additional_rebate_disc") or 0

            if is_fixed:
                # memastikan default diskon dan rabate menjadi 0 
                self.doc.discount_percent = self.doc.discount_percent_rebate = 0

            for item in self.doc.items:
                self.doc.round_floats_in(item)
                item.rebate_amount = 0
                # pastikan tidak ada doble rabate dan discount
                if not apply_rebate:
                    item.rebate = item.rebate_rate = 0
                else:
                    item.discount_percentage = item.discount_amount = 0

                # set nilai rebate sesuai dengan rebate max dan fix dari doctype item 
                item.rebate_max, item.rebate_fix = frappe.get_cached_value("Item", item.item_code, ["custom_rabat_max", "custom_cb"]) or [0, 0]

                if is_fixed:
                    item.set(field, item.rebate_fix + add_rebate_disc)
                elif is_max_applied and item.get("rebate_max") and item.get(field) > item.rebate_max:
                    item.set(field, item.rebate_max)

                if item.discount_percentage == 100:
                    item.rate = 0.0
                elif item.price_list_rate:
                    item.rate = item.price_list_rate
                    if not item.rate or item.discount_percentage > 0:
                        item.rate = flt(
                            item.price_list_rate * (1.0 - (item.discount_percentage / 100.0)),
                            item.precision("rate"),
                        )

                        item.discount_amount = item.price_list_rate * (item.discount_percentage / 100.0)

                    elif item.discount_amount and item.pricing_rules:
                        item.rate = item.price_list_rate - item.discount_amount

                    if item.rebate_rate and not item.rebate:
                        item.rebate = flt(item.rebate_rate / item.price_list_rate * 100, item.precision("rebate"))
                    elif not item.rebate_rate:
                        item.rebate_rate = flt(item.price_list_rate * item.rebate / 100, item.precision("rebate_rate"))

                if item.doctype in [
                    "Pre Order Item"
                    "Quotation Item",
                    "Sales Order Item",
                    "Delivery Note Item",
                    "Sales Invoice Item",
                    "POS Invoice Item",
                    "Purchase Invoice Item",
                    "Purchase Order Item",
                    "Purchase Receipt Item",
                ]:
                    item.rate_with_margin, item.base_rate_with_margin = self.calculate_margin(item)
                    if flt(item.rate_with_margin) > 0:
                        item.rate = flt(
                            item.rate_with_margin * (1.0 - (item.discount_percentage / 100.0)),
                            item.precision("rate"),
                        )

                        if item.discount_amount and not item.discount_percentage:
                            item.rate = item.rate_with_margin - item.discount_amount
                        else:
                            item.discount_amount = item.rate_with_margin - item.rate

                    elif flt(item.price_list_rate) > 0:
                        item.discount_amount = item.price_list_rate - item.rate
                        
                elif flt(item.price_list_rate) > 0 and not item.discount_amount:
                    item.discount_amount = item.price_list_rate - item.rate

                item.net_rate = item.rate

                if (
                    not item.qty
                    and self.doc.get("is_return")
                    and self.doc.get("doctype") != "Purchase Receipt"
                ):
                    item.amount = flt(-1 * item.rate, item.precision("amount"))
                elif not item.qty and self.doc.get("is_debit_note"):
                    item.amount = flt(item.rate, item.precision("amount"))
                else:
                    item.amount = flt(item.rate * item.qty, item.precision("amount"))
                    item.rebate_amount = flt(item.rebate_rate * item.qty, 
                        item.precision("rebate_amount"))
                    
                item.net_amount = item.amount

                self._set_in_company_currency(
                    item, ["price_list_rate", "rate", "net_rate", "amount", "net_amount", "rebate_amount"]
                )

                item.item_tax_amount = 0.0

    # update untuk menghitung total rabat
    def calculate_net_total(self):
        self.doc.total_qty = (
            self.doc.total
        ) = self.doc.base_total = self.doc.net_total = self.doc.base_net_total = 0.0
        self.doc.base_rebate_total = self.doc.rebate_total = 0.0

        for item in self._items:
            self.doc.total += item.amount
            self.doc.total_qty += item.qty
            self.doc.base_total += item.base_amount
            self.doc.net_total += item.net_amount
            self.doc.base_net_total += item.base_net_amount
            self.doc.base_rebate_total += item.rebate_amount
            self.doc.rebate_total += item.rebate_amount

        self.doc.round_floats_in(self.doc, [
            "total", "base_total", "net_total", "base_net_total", 
            "base_rebate_total", "rebate_total"])