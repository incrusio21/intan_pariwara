# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _

def get_data(data):
    data.non_standard_fieldnames["Usulan Tambahan Rabat"] = "sales_order"
    for link in [{"label": _("Fulfillment"), "items": ["Usulan Tambahan Rabat"]}]:
        # Cari transaksi dengan label "Reference"
        reference_transaction = next((t for t in data.transactions if t["label"] == link["label"]), None)

        if reference_transaction:
            # Ubah nilai items
            reference_transaction["items"].extend(link["items"]) # Ganti dengan item yang kamu inginkan
        else:
            data.transactions.append(link)

    return data