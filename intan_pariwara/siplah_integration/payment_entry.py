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
def post_payment(jumlah=None,tanggal=None,mop=None,no_siplah=None,biaya=None,sinv_name=None,customer=None, ref_no=None,va_number=None):
	
	if not jumlah:
		frappe.throw("Parameter Jumlah mandatory")

	if not tanggal:
		frappe.throw("Parameter Tanggal mandatory")

	if not mop:
		frappe.throw("Parameter MOP mandatory")

	
	body = frappe._dict({
			"no_siplah": no_siplah,
			"jumlah": jumlah,
			"biaya": biaya,
			"tanggal": tanggal,
			"mop":mop,
			"ref_no": ref_no or va_number or no_siplah,
		})
	
	ref_doc_id = ""
	ref_type = ""

	# PE API
	# 1. No SIPLAH : find Sales Invoice or Sales Order that linked with No SIPLAH
	# 2. SINV Name : use SINV Name as reference
	# 3. VA Number : find VA Number in Sales Invoice if not find in Customer

	if no_siplah:
		ref_doc_id, ref_type = get_sinv_siplah(no_siplah)

	if ref_doc_id == "" and sinv_name:
		ref_type = "Sales Invoice"
		ref_doc_id = sinv_name

	if ref_doc_id == "" and va_number:
		if frappe.db.exists("Sales Invoice", {"va_number":va_number}, "name"):
			ref_type = "Sales Invoice"
			ref_doc_id = frappe.get_value("Sales Invoice", {"va_number":va_number},"name")

		if frappe.db.exists("Customer", {"va_number":va_number}, "name"):
			customer = frappe.get_value("Customer", {"va_number":va_number}, "name")

	pe_dict = {}

	if ref_doc_id:
		pe_dict = create_payment_entry(body, ref_type=ref_type, ref_doc_id=ref_doc_id)

	if ref_doc_id == "" and customer:
		pe_dict = create_payment_entry(body, customer=customer)
		
	if ref_doc_id == "" and customer == "":
		frappe.throw("Tidak menemukan Customer atau Sales Invoice.")

	return pe_dict or body

def get_sinv_siplah(no_siplah):
	if frappe.db.exists("Sales Invoice",{"no_siplah": no_siplah}):
		return frappe.db.get_value("Sales Invoice",{"no_siplah":no_siplah},"name"),"Sales Invoice"

	if frappe.db.exists("Sales Order",{"custom_no_siplah": no_siplah},"name"):
		return frappe.db.get_value("Sales Order",{"custom_no_siplah":no_siplah},"name"), "Sales Order"


	frappe.throw("No SIPLAH tidak ditemukan di Invoice/Order manapun.") 

def create_payment_entry(args, ref_type=None, ref_doc_id=None, customer=None):
	
	ref_doc = None
	if ref_doc_id:
		ref_doc = frappe.get_doc(ref_type, ref_doc_id)
	
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

	pe.party = ref_doc.customer if ref_doc else c.name
	pe.party_name = ref_doc.customer_name if ref_doc else c.customer_name
	# pe.paid_from = ref_doc.debit_to if ref_doc else frappe.get_value("Master SIPLAH","Payment Entry Default Piutang","account")
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
	
	pe.reference_no = args.ref_no or "{} - {}".format(args.mop, ref_doc.customer_name if ref_doc else c.customer_name) 
	
	pe.reference_date = args.tanggal
	pe.book_advance_payments_in_separate_party_account = True
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
	

	if ref_doc:
		if ref_type == "Sales Invoice":
			if allocated_amount > ref_doc.outstanding_amount:
				allocated_amount = ref_doc.outstanding_amount
		else:
			allocated_amount = ref_doc.grand_total
		
		pe.append("references",
			{
				"reference_doctype":ref_type,
				"reference_name": ref_doc_id,
				"allocated_amount": flt(allocated_amount),
				"account": ref_doc.debit_to if ref_type == "Sales Invoice" else pe.paid_from,
				"payment_term": ""
			})

	# return pe.as_dict()

	pe.save()
	pe.submit()
	return "Payment Entry {} berhasil terbentuk".format(pe.name)
