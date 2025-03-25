# Copyright (c) 2024, DAS and Contributors
# License: GNU General Public License v3. See license.txt

from erpnext.selling.doctype.sales_order.sales_order import SalesOrder

from intan_pariwara.controllers.account_controller import AccountsController

class SalesOrder(AccountsController, SalesOrder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_updater = [
            {
                "source_dt": "Sales Order Item",
                "target_dt": "Pre Order Item",
                "join_field": "custom_pre_order_item",
                "target_field": "ordered_qty",
                "target_parent_dt": "Pre Order",
                "target_parent_field": "per_ordered",
                "target_ref_field": "qty",
                "source_field": "qty",
                "percent_join_field_parent": "pre_order",
                "status_field": "status",
				"keyword": "Ordered",
            }
        ]

    def update_prevdoc_status(self, flag=None):
        super().update_prevdoc_status(flag)

        self.update_qty()
        self.validate_qty()