import frappe
from intan_pariwara.siplah_integration.payment_entry import post_payment

def test():
    # test PE
    amount = 2000000
    tgl = frappe.utils.nowdate()
    mop = "VA MANDIRI IP"
    sinv_name = "ACC-SINV-2025-00078"

    post_payment(jumlah=amount, tanggal=tgl, mop=mop,sinv_name=sinv_name)	