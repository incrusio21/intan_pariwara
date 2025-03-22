import frappe
import json
from frappe.utils import flt, getdate
"""
	SIPLAH will push No SIPLAH, Amount, and Costs (Deduction)
	
	From no_siplah function fill reference ID if not found return error

	payment_type : Receive
	company : Intan Pariwara Vitarana
	
	Body Param:
	no_siplah : txt
	paid_amount : currency
	biaya : dict / json
	tanggal : date
	"""

@frappe.whitelist()
def post_payment(no_siplah,jumlah,tanggal,biaya=None):
	
	
	body = frappe._dict({
			"no_siplah": no_siplah,
			"jumlah": jumlah,
			"biaya": dict(json.loads(biaya)) if biaya else None,
			"tanggal": tanggal
		})
	
	sinv_id = get_sinv_siplah(no_siplah)
	
	pe_dict = create_payment_entry(body, sinv_id)

	return pe_dict or body

def get_sinv_siplah(no_siplah):
	if frappe.db.exists("Sales Invoice",{"no_siplah": no_siplah}):
		return frappe.db.get_value("Sales Invoice",{"no_siplah":no_siplah},"name")

	frappe.throw("No SIPLAH tidak ditemukan di Invoice manapun.") 

def create_payment_entry(args, sinv_id):
	sinv = frappe.get_doc("Sales Invoice", sinv_id)
	pe = frappe.new_doc("Payment Entry")
	pe.company = "Intan Pariwara Vitarana"
	pe.naming_series = "ACC-PAY-.YYYY.-"
	pe.payment_type = "Receive"
	pe.posting_date = args.tanggal
	pe.party_type = "Customer"
	pe.party = sinv.customer
	pe.party_name = sinv.customer_name
	pe.paid_from = sinv.debit_to
	pe.paid_to = frappe.get_value("Master SIPLAH","Payment Entry Hutang Titipan","account")
	pe.paid_amount = flt(args.jumlah)
	pe.received_amount = flt(args.jumlah)
	pe.paid_from_account_currency = "IDR"
	pe.paid_to_account_currency = "IDR"
	pe.source_exchange_rate = 1
	pe.target_exchange_rate = 1
	pe.no_siplah = args.no_siplah
	pe.reference_no = args.no_siplah
	pe.reference_date = args.tanggal
	pe.book_advance_payments_in_separate_party_account = 0


	sum_biaya = 0
	if args.biaya:
		for acc,amt in args.biaya.items():
			if frappe.get_value("Master SIPLAH",acc,"account"):
				pe.append("deductions",{
					"account": frappe.get_value("Master SIPLAH",acc,"account"),
					"cost_center": "Main - IPV",
					"amount": flt(amt)
				})
				sum_biaya += flt(amt)
	
	allocated_amount = flt(args.jumlah) - sum_biaya
	pe.append("references",
		{
			"reference_doctype":"Sales Invoice",
			"reference_name": sinv_id,
			"allocated_amount": flt(allocated_amount),
			"account": sinv.debit_to,
			"payment_term": ""
		})

	# return pe.as_dict()

	pe.save()
	pe.submit()
	return "Payment Entry {} berhasil terbentuk".format(pe.name)