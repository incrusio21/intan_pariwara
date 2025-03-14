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
        url.svg(stream, scale=4, quiet_zone=2, module_color="#222")
        svg = stream.getvalue().decode().replace("\n", "")
        svg = b64encode(svg.encode())
    finally:
        stream.close()

    return svg.decode()