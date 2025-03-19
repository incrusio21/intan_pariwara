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
			"debits": dict(json.loads(debits)),
			"credits": dict(json.loads(credits)),
			"tanggal": tanggal
		})
	
	jv_dict = create_journal_entry(body)

	return jv_dict or body

def create_journal_entry(args):
	
	jv = frappe.new_doc("Journal Entry")
	jv.company = "Intan Pariwawara Vitarana"
	jv.voucher_type = "Journal Entry"
	jv.posting_date = args.tanggal
	jv.no_siplah = args.no_siplah

	# dana titipan
	for acc, amt in args.debits.items():
		if frappe.get_value("Master SIPLAH",acc,"account"):
			jv.append("accounts",{
				"account":  frappe.get_value("Master SIPLAH", acc,"account"),
				"cost_center": "Main - IPV",
				"debit_in_account_currency": amt,
				"debit": amt
			})


	for acc,amt in args.credits.items():
		if frappe.get_value("Master SIPLAH",acc,"account"):
			jv.append("accounts",{
				"account": frappe.get_value("Master SIPLAH",acc,"account"),
				"cost_center": "Main - IPV",
				"credit": amt,
				"credit_in_account_currency": amt
			})

	"""
	try:
		jv.save()
		jv.submit()
	except Exception as e:
		frappe.log_error(e,"Journal Entry API SIPLAH Error")
		raise e
	"""

	if jv.name:
		return "Journal Entry {} created".format(jv.name)

	else:
		frappe.throw("Terjadi kesalahan ketika memproses Journal Entry")