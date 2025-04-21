# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt
from base64 import b64encode
from io import BytesIO

import frappe
from frappe import _

def format_nomor_telepon(nomor_telepon):
    if not nomor_telepon:
        frappe.throw(_("Please fill in your phone number."))
        
    if nomor_telepon.startswith('0'):
        return '62' + nomor_telepon[1:]
    
    return nomor_telepon

def get_qr_svg(data):
    """Get SVG code to display Qrcode for OTP."""
    from pyqrcode import create as qrcreate

    url = qrcreate(data)
    svg = ""
    stream = BytesIO()
    try:
        url.svg(stream, scale=4, quiet_zone=1, module_color="#222")
        svg = stream.getvalue().decode().replace("\n", "")
        svg = b64encode(svg.encode())
    finally:
        stream.close()

    return svg.decode()

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

def qty_koli(qty, qty_per_koli):
    full_packs, quantity = divmod(qty, qty_per_koli)

    return {"utuh": full_packs, "retail": quantity}