# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe

def get_item_per_koli(items):
    """Get Item List Per Koli."""
    target = []
    for d in items:
        item = d.as_dict().copy()

        quantity = item.qty
        qty_per_koli = frappe.get_cached_value("Item", item.item_code, "qty_per_koli")
        if qty_per_koli:
            # Hitung kemasan utuh dan sisa
            full_packs, quantity = divmod(quantity, qty_per_koli)
            # Tambahkan kemasan utuh ke package
            target.extend([{**item, "qty": qty_per_koli} for _ in range(int(full_packs))])
        else:
            target.append(item)
            quantity = 0

        # Tambahkan sisa ke retail
        if quantity > 0:
            item.is_retail = 1
            target.append({**item, "qty": quantity})

    return target

def same_item_price(items):
    """Get Item List Per Koli."""
    target = {}
    for d in items:
        item = target.setdefault((d.item_code, d.price_list_rate), frappe._dict({ **d.as_dict(), "qty": 0}))
        item["qty"] += d.qty

    return target

def qty_koli(qty, qty_per_koli):
    full_packs = quantity = 0
    if qty_per_koli:
        full_packs, quantity = divmod(qty, qty_per_koli)

    return {"utuh": full_packs, "retail": quantity}