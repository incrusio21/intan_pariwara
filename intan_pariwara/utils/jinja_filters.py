# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def format_nomor_telepon(nomor_telepon):
    if not nomor_telepon:
        frappe.throw(_("Please fill in your phone number."))
        
    if nomor_telepon.startswith('0'):
        return '62' + nomor_telepon[1:]
    
    return nomor_telepon