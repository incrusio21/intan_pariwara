import frappe
import requests
import json
from frappe.utils import flt, get_datetime, now_datetime
from datetime import datetime

from intan_pariwara import load_env

@frappe.whitelist()
def get_list_siplah(customer=None, relasi=None):

	token, tokenExp = get_token()

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
		filtered_order = list_order_id

		# remove No SIPLAH that used by another Sales Order
		# for o in list_order_id:
		# 	if not frappe.db.exists("Sales Order",{"custom_no_siplah":o["nomor_order"],"docstatus":["<","2"]}):
		# 		filtered_order.append({
		# 			"nomor_order":o["nomor_order"],
		# 			"janji_bayar":o["janji_bayar"]
		# 		})

	if filtered_order == []:
		frappe.msgprint("Tidak ada No SIPLAH yang ditemukan")

	return filtered_order

@frappe.whitelist()
def get_transaction_details(no_siplah, siplah_list, doc=None, docname=None):
	
	if not doc and docname:
		doc = frappe.get_doc("Sales Order", docname)

	siplah_items = get_siplah_items(no_siplah, doc.selling_price_list)

	# if Pre Order Item == SIPLAH Item
	# 	add to Sales Order Item:
	#		if PreOrder Item Qty < SIPLAH Item Qty -> SIPLAH Wins
	#		if PreOrder Item Price < SIPLAH Item Price -> SIPLAH Wins
	# else dont add item to table
	# if SIPLAH Item not in Pre Order add to table
	
	doc.items = []
	doc.custom_no_siplah = no_siplah
	# 2025-03-28: disable feature get janji bayar overwrite to payment date
	doc.payment_date = doc.payment_date
	
	pre_old_items = frappe.get_all("Pre Order Item", filters={"parent": doc.pre_order}, 
		fields=[
			"item_code", "item_name", "description", "price_list_rate", "uom", "warehouse",
			"name as custom_pre_order_item", "parent as custom_pre_order"]) \
		if doc.pre_order else []
	
	pre_old_items_dict = {item.item_code: item for item in pre_old_items}

	for sitems in siplah_items:
		if (item := pre_old_items_dict.get(sitems['item_code'])):
			# Update existing item
			item.qty = sitems['qty']
			item.rate = sitems['price']
			item.delivery_date = doc.delivery_date
			doc.append("items", item)
		else:
			# Create new item
			doc.append("items", {
				"item_code": sitems["item_code"],
				"item_name": sitems["item_name"],
				"description": sitems["item_name"],  # Duplikasi item_name ke description
				"rate": sitems["price"],
				"price_list_rate": sitems["price_list_rate"],
				"delivery_date": doc.delivery_date,
				"uom": sitems["uom"],
				"qty": sitems["qty"]
			})

	doc.siplah_json = None
	
	if not doc.payment_schedule:
		doc.append("payment_schedule",{
			"due_date": doc.payment_date,
			"invoice_portion": 100
		})
	elif len(doc.payment_schedule) == 1:
		doc.payment_schedule[0].due_date = doc.payment_date
	
	return doc

def load_siplah_items(no_siplah, doc=None, docname=None):
	if not doc and docname:
		doc = frappe.get_doc("Sales Order", docname)

	# just in case IP need table to compare items
	siplah_items = get_siplah_items(no_siplah, doc.selling_price_list)
	doc.custom_no_siplah = no_siplah
	doc.tabel_siplah_items = []
	for sitems in siplah_items:
		doc.append("tabel_siplah_items",{
				"item_code": sitems["item_code"],
				"item_name": sitems["item_name"],
				"qty": sitems["qty"],
				"rate": sitems["price"],
			})
	doc.siplah_json = None

	return doc

def get_janji_bayar(no_siplah, siplah_list):
	siplah_dicts = json.loads(siplah_list)
	for x in siplah_dicts:
		if x['nomor_order'] == no_siplah:
			return x['janji_bayar']
	return None

@frappe.whitelist()
def get_siplah_items(no_siplah,price_list):
	token, tokenExp = get_token()
	
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
				"price": flt(t['price']),
				"uom": uom,
				"item_name": item_name or t['name'],
				"description": t['name'],
				"price_list_rate": flt(frappe.get_value("Item Price", {"item_code":sku,"price_list":price_list}, "price_list_rate")) or 0
			})

	return list_items


# Sales Invoice on submit generate VA Number
def get_va_number(doc,method):
	if not doc.no_siplah:
		url = "https://va.intanonline.com/mandiri/generate-va.php"
		headers = {"Content-Type":"application/json"}
		payload = json.dumps({
    	    "nota_no": doc.name,
		    "customer_name" : doc.customer_name,
		    "secret_key": "080042cad6356ad5dc0a720c18b53b8e53d4c274",
		    "bill": 0,
		    "va_type": "INV",
		    "cust_id": doc.customer
		})
		response = requests.request("POST", url, headers=headers, data=payload)
		make_log("POST", url, str(headers), str(payload), str(response.text))
		if response.text and response.text != "":
			try:
				resp_content = json.loads(response.text)
				doc.db_set("va_number", resp_content['virtual_account_number'])
			except Exception as e:
				raise e
		else:
			frappe.throw("VA Number API Error")

def make_log(req_type, url, headers, payload, response, token=None, token_exp=None,api_type="IP SIPLAH"):
	doc = frappe.new_doc("SIPLAH API Log")
	doc.request_type = req_type
	doc.url = url
	doc.headers = headers
	doc.payload = payload
	doc.response = response
	doc.api_type = api_type
	if token:
		doc.token = token
	if token_exp:
		doc.token_exp = token_exp
	doc.save(ignore_permissions=True)

def is_token_expired():

	siplah_secrets = {"siplah_token": frappe.cache.get_value("siplah_token"), "siplah_token_exp": frappe.cache.get_value("siplah_token_exp")}
	if siplah_secrets["siplah_token_exp"]:
		t_old = siplah_secrets["siplah_token_exp"].replace("Z","")
		
		if t_old:
			print("is_exp", get_datetime(datetime.now()),get_datetime(t_old))

			if get_datetime(datetime.now()) > get_datetime(t_old):
				return True
		else:
			return False
	else:
		return True

def get_token():
	siplah_secrets = {}
	token, tokenExp = "",""
	if is_token_expired():
		auth = get_auth()
		token = auth['token']
		tokenExp = auth['expiredAt']
		frappe.cache.set_value("siplah_token", token)
		frappe.cache.set_value("siplah_token_exp", tokenExp.split("Z")[0])
	else:
		token = frappe.cache.get_value("siplah_token")
		tokenExp = frappe.cache.get_value("siplah_token_exp")

	return token, tokenExp
	

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