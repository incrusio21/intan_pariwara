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
def post_payment(jumlah,tanggal,mop,no_siplah=None,biaya=None,sinv_name=None,customer=None, ref_no=None,va_number=None):
	
	
	body = frappe._dict({
			"no_siplah": no_siplah,
			"jumlah": jumlah,
			"biaya": biaya,
			"tanggal": tanggal,
			"mop":mop,
			"ref_no": ref_no
		})
	
	sinv_id = ""
	if no_siplah:
		sinv_id = get_sinv_siplah(no_siplah)

	if sinv_id == "" and sinv_name:
		sinv_id = sinv_name

	if sinv_id == "" and va_number:
		sinv_id = frappe.get_value("Sales Invoice", {"va_number":va_number},"name") or ""

	pe_dict = {}
	if sinv_id:
		pe_dict = create_payment_entry(body, sinv_id=sinv_id)

	if sinv_id == "" and customer:
		pe_dict = create_payment_entry(body, customer=customer)
		

	return pe_dict or body

def get_sinv_siplah(no_siplah):
	if frappe.db.exists("Sales Invoice",{"no_siplah": no_siplah}):
		return frappe.db.get_value("Sales Invoice",{"no_siplah":no_siplah},"name")

	frappe.throw("No SIPLAH tidak ditemukan di Invoice manapun.") 

def create_payment_entry(args, sinv_id=None, customer=None):
	sinv = None
	if sinv_id:
		sinv = frappe.get_doc("Sales Invoice", sinv_id)
	
	c = None
	if customer:
		c = frappe.get_doc("Customer", customer)

	pe = frappe.new_doc("Payment Entry")
	pe.company = "Intan Pariwara Vitarana"
	pe.naming_series = "ACC-PAY-.YYYY.-"
	pe.payment_type = "Receive"
	pe.mode_of_payment = args.mop
	pe.posting_date = args.tanggal
	pe.party_type = "Customer"

	pe.party = sinv.customer if sinv else c.name
	pe.party_name = sinv.customer_name if sinv else c.customer_name
	# pe.paid_from = sinv.debit_to if sinv else frappe.get_value("Master SIPLAH","Payment Entry Default Piutang","account")
	# force paid from into Account Unallocated
	pe.paid_from = frappe.get_value("Master SIPLAH","Payment Entry Default Piutang","account")
	
	pe.paid_to = frappe.get_value("Master SIPLAH","Payment Entry Hutang Titipan","account")
	
	if args.mop:
		pe.paid_to = frappe.get_value("Mode of Payment Account",{"company":pe.company,"parent":args.mop},"default_account") or pe.paid_to
	pe.paid_amount = flt(args.jumlah)
	pe.received_amount = flt(args.jumlah)
	pe.paid_from_account_currency = "IDR"
	pe.paid_to_account_currency = "IDR"
	pe.source_exchange_rate = 1
	pe.target_exchange_rate = 1
	pe.no_siplah = args.no_siplah
	pe.reference_no = sinv.va_number or args.ref_no or args.no_siplah  or "{} - {}".format(args.mop, customer.name) 
	pe.reference_date = args.tanggal
	pe.book_advance_payments_in_separate_party_account = 1
	pe.advance_reconciliation_takes_effect_on = "Reconciliation Date"


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
	if sinv:
		if allocated_amount > sinv.outstanding_amount:
			allocated_amount = sinv.outstanding_amount
		
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
