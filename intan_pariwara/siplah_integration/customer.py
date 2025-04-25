import frappe
import json
import requests

from intan_pariwara.siplah_integration.sales_order import make_log
@frappe.whitelist()
def get_va_number(docname):
	doc = frappe.get_doc("Customer", docname)
	
	url = "https://va.intanonline.com/mandiri/generate-va.php"
	headers = {"Content-Type":"application/json"}
	payload = json.dumps({
	    "nota_no": "",
	    "customer_name" : doc.customer_name,
	    "secret_key": "080042cad6356ad5dc0a720c18b53b8e53d4c274",
	    "bill": 0,
	    "va_type": "CUST",
	    "cust_id": doc.name
	})
	response = requests.request("POST", url, headers=headers, data=payload)
	make_log("POST", url, headers=str(headers), payload=str(payload), response=str(response.text),api_type="VA Mandiri")

	if response.text and response.text != "":
		try:
			resp_content = json.loads(response.text)
			doc.va_number = resp_content['virtual_account_number']
			doc.save()
		except Exception as e:
			raise e
	else:
		frappe.throw("VA Number API Error")