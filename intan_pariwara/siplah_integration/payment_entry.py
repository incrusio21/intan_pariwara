import frappe
import json
from frappe.utils import flt
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
			"biaya": dict(json.loads(biaya)),
			"tanggal": tanggal
		})
	
	# sinv_id = get_sinv_siplah(no_siplah)
	sinv_id = "ACC-SINV-2025-00024" # test
	
	pe_dict = create_payment_entry(body, sinv_id)

	return pe_dict or body

def get_sinv_siplah(no_siplah):
	if frappe.db.exists("Sales Invoice",{"custom_no_siplah": no_siplah}):
		return frappe.db.get_value("Sales Invoice",{"custom_no_siplah":no_siplah},"name")

	frappe.throw("No SIPLAH tidak ditemukan di Invoice manapun.") 

def create_payment_entry(args, sinv_id):
	sinv = frappe.get_doc("Sales Invoice", sinv_id)
	pe = frappe.new_doc("Payment Entry")
	pe.company = "Intan Pariwawara Vitarana"
	pe.payment_type = "Receive"
	pe.posting_date = args.tanggal
	pe.party_type = "Customer"
	pe.party = sinv.customer
	pe.party_name = sinv.customer_name
	pe.paid_from = sinv.debit_to
	pe.paid_to = frappe.get_value("Master SIPLAH","Payment Entry Hutang Titipan","account")
	pe.paid_amount = flt(args.jumlah)
	pe.received_amount = flt(args.jumlah)
	pe.source_exchange_rate = 1
	pe.target_exchange_rate = 1

	pe.append("references",{
			"reference_doctype":"Sales Invoice",
			"reference_name": sinv.name,
			"due_date": sinv.due_date,
			"total_amount": sinv.rounded_total,
			"outstanding_amount": sinv.outstanding_amount,
			"allocated_amount": flt(args.jumlah)
		})

	if args.biaya:
		for acc,amt in args.biaya.items():
			if frappe.get_value("Master SIPLAH",acc,"account"):
				pe.append("deductions",{
					"account": frappe.get_value("Master SIPLAH",acc,"account"),
					"cost_center": "Main - IPV",
					"amount": amt
				})

	# pe.save()
	# pe.submit()
	return pe.as_dict()
