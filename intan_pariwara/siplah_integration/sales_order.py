import frappe
import requests
import json
from frappe.utils import flt, get_datetime, now_datetime
from datetime import datetime

from intan_pariwara import load_env
token = ""
tokenExp = ""

@frappe.whitelist()
def get_list_siplah(customer=None, relasi=None):

	if is_token_expired():
		auth = get_auth()
		token = auth['token']
		tokenExp = auth['expiredAt']
		frappe.cache.set_value("siplah_token", auth['token'])
		frappe.cache.set_value("siplah_token_exp", auth['expiredAt'].split("Z")[0])
	else:
		token = frappe.cache.get_value("siplah_token")
		tokenExp = frappe.cache.get_value("siplah_token_exp")
	
	nss = None
	url = ""

	if relasi:
		nss = frappe.get_value("Customer", customer, "custom_nss")
		if not nss:

			url = "{}/erp/v1/transactionsone/{}".format(load_env().BASE_URL,customer)
		else:
			url = "{}/erp/v1/transactions/{}/{}".format(load_env().BASE_URL,relasi,nss)
	else:
		url = "{}/erp/v1/transactionsone/{}".format(load_env().BASE_URL,customer)

	headers = {
		'Content-Type': 'application/json',
		'Authorization': "Bearer {}".format(token)
	}

	payload = {}

	response = requests.request("GET", url, headers=headers, data=payload)
	
	make_log("GET", url, str(headers), str(payload), str(response.text), str(token), str(tokenExp))

	list_order_id = []
	filtered_order = []
	list_trans = None
	err_msg = ""
	if response.text and response.text != "":
		try:
			list_trans = json.loads(response.text)
		except Exception as e:
			frappe.log_error(str(e), "ERROR API SIPLAH")
			frappe.msgprint("Tidak ada No SIPLAH yang ditemukan")
			return []

		for t in list_trans['data']:
			list_order_id.append({
					"nomor_order": str(t['nomor_order']),
					"janji_bayar":str(t['janji_bayar'])
				})
		
		for o in list_order_id:
			if not frappe.db.exists("Sales Order",{"custom_no_siplah":o["nomor_order"]}):
				filtered_order.append({
					"nomor_order":o["nomor_order"],
					"janji_bayar":o["janji_bayar"]

					})

	if filtered_order == []:
		frappe.msgprint("Tidak ada No SIPLAH yang ditemukan")

	return filtered_order

@frappe.whitelist()
def get_transaction_details(no_siplah,price_list):

	auth = get_auth()
	token = auth['token']
	
	url = "{}/erp/v1/transaction/details/{}".format(load_env().BASE_URL,no_siplah)
	
	headers = {
		'Content-Type': 'application/json',
		'Authorization': "Bearer {}".format(token)
	}

	payload = {}
	
	response = requests.request("GET", url, headers=headers, data=payload)
	
	list_items = []

	if response.text and response.text != "":
		list_resp = json.loads(response.text)

		for t in list_resp['data']:
			sku = t['sku'].split("_")[0]
			uom = frappe.get_value("Item", sku, "stock_uom") or ""
			item_name = frappe.get_value("Item", sku, "item_name") or None
			list_items.append({
				"item_code": sku,
				"qty": t['qty'],
				"price":flt(t['price']),
				"uom": uom,
				"item_name": item_name or t['name'],
				"description": t['name'],
				"price_list_rate": frappe.get_value("Item Price",{"item_code":sku,"price_list":price_list},"price_list_rate") or 0
				})

	return list_items

def make_log(req_type, url, headers, payload, response, token, token_exp):
	doc = frappe.new_doc("SIPLAH API Log")
	doc.request_type = req_type
	doc.url = url
	doc.headers = headers
	doc.payload = payload
	doc.response = response
	doc.token = token
	doc.token_exp = token_exp
	doc.save(ignore_permissions=True)

def is_token_expired():
	if frappe.cache.get_value("siplah_token_exp"):
		t_old = frappe.cache.get_value("siplah_token_exp").replace("Z","")
		
		if t_old:
			print("is_exp", get_datetime(datetime.now()),get_datetime(t_old))

			if get_datetime(datetime.now()) > get_datetime(t_old):
				return True
		else:
			return False
	else:
		return True
	

def get_auth():
	env = load_env()
	
	url = "{}/erp/v1/auth".format(env.BASE_URL)
	headers = {
		'Content-Type': 'application/json'
	}
	payload = json.dumps({
		"clientId": env.CLIENT_ID,
		"clientSecret": env.CLIENT_SECRET
	})

	resp = requests.request("POST",url,headers=headers,data=payload)
	return json.loads(resp.text)

'''
	bench execute intan_pariwara.siplah_integration.sales_order.auth
'''