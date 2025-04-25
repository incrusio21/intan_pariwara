import frappe
import json
from frappe.utils import flt
"""
	SIPLAH will push No SIPLAH, Debit COA and Amount, Credit COA and Amount
		
	Body Param:
	no_siplah : txt
	tanggal : date
	debits : json/dict
	credits : json/dict
	"""

@frappe.whitelist()
def post_journal(no_siplah,tanggal,debits,credits):
	
	body = frappe._dict({
			"no_siplah": no_siplah,
			"debits": debits,
			"credits": credits,
			"tanggal": tanggal
		})
	
	msg = create_journal_entry(body)

	return msg or body

def create_journal_entry(args):
	
	jv = frappe.new_doc("Journal Entry")
	jv.company = "Intan Pariwara Vitarana"
	jv.voucher_type = "Journal Entry"
	jv.posting_date = args.tanggal
	jv.no_siplah = args.no_siplah
	total_debit = 0
	total_credit = 0
	# dana titipan
	for acc, amt in args.debits.items():
		if frappe.get_value("Master SIPLAH",acc,"account"):
			jv.append("accounts",{
				"account":  frappe.get_value("Master SIPLAH", acc,"account"),
				"cost_center": "Main - IPV",
				"debit_in_account_currency": flt(amt),
				"debit": flt(amt),
				"user_remark": args.no_siplah
			})
			total_debit += flt(amt)


	for acc,amt in args.credits.items():
		if frappe.get_value("Master SIPLAH",acc,"account"):
			if flt(amt) > 0:
				jv.append("accounts",{
					"account": frappe.get_value("Master SIPLAH",acc,"account"),
					"cost_center": "Main - IPV",
					"credit": amt,
					"credit_in_account_currency": amt,
					"user_remark": args.no_siplah
				})
			total_credit += flt(amt)

	# return jv.as_dict()

	if total_debit != total_credit:
		frappe.throw("Jumlah credit dan debit tidak sama.")

	try:
		jv.save()
		jv.submit()
	except Exception as e:
		frappe.log_error(e,"Journal Entry API SIPLAH Error")
		raise e
	
	if jv.name:
		return "Journal Entry {} created".format(jv.name)

	else:
		frappe.throw("Terjadi kesalahan ketika memproses Journal Entry")