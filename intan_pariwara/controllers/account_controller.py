# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

class AccountsController:
    def calculate_taxes_and_totals(self):
        from intan_pariwara.controllers.taxes_and_totals import calculate_taxes_and_totals

        calculate_taxes_and_totals(self)

        if self.doctype in (
            "Sales Order",
            "Delivery Note",
            "Sales Invoice",
            "POS Invoice",
        ):
            self.calculate_commission()
            self.calculate_contribution()