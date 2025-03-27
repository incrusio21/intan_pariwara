__version__ = "0.0.1"


import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr
from frappe.utils.data import flt

from erpnext import get_default_company
from erpnext.accounts import party as party_file
from erpnext.selling.doctype.quotation import quotation
from erpnext.stock import get_item_details

from erpnext.setup.doctype.brand.brand import get_brand_defaults
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.stock.doctype.item_manufacturer.item_manufacturer import get_item_manufacturer_part_no
from intan_pariwara.controllers.queries import get_price_list_fund


def load_env():
	"""Returns the intan pariwara env variable"""
	from dotenv import dotenv_values
	from pathlib import Path

	if not frappe.flags.intan_pariwara:
		frappe.flags.intan_pariwara = frappe._dict(dotenv_values(Path(__file__).parent / ".env"))

	return frappe.flags.intan_pariwara


def is_delivery_account_enabled(company):
	if not company:
		company = "_Test Company" if frappe.flags.in_test else get_default_company()

	if not hasattr(frappe.local, "enable_delivery_account"):
		frappe.local.enable_delivery_account = {}

	if company not in frappe.local.enable_delivery_account:
		frappe.local.enable_delivery_account[company] = (
			frappe.get_cached_value("Company", company, "custom_enable_delivery_account") or 0
		)

	return frappe.local.enable_delivery_account[company]

# overwrite fungsi

# custom menambahkan sales person berdasarkan custom field
def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
    customer = quotation._make_customer(source_name, ignore_permissions)
    ordered_items = frappe._dict(
        frappe.db.get_all(
            "Sales Order Item",
            {"prevdoc_docname": source_name, "docstatus": 1},
            ["item_code", "sum(qty)"],
            group_by="item_code",
            as_list=1,
        )
    )

    selected_rows = [x.get("name") for x in frappe.flags.get("args", {}).get("selected_items", [])]

    def set_missing_values(source, target):
        if customer:
            target.customer = customer.name
            target.customer_name = customer.customer_name

            # sales team
            if not target.get("sales_team"):
                for d in customer.get("sales_team") or []:
                    target.append(
                        "sales_team",
                        {
                            "sales_person": d.sales_person,
                            "allocated_percentage": d.allocated_percentage or None,
                            "commission_rate": d.commission_rate,
                        },
                    )

        if source.referral_sales_partner:
            target.sales_partner = source.referral_sales_partner
            target.commission_rate = frappe.get_value(
                "Sales Partner", source.referral_sales_partner, "commission_rate"
            )

        target.flags.ignore_permissions = ignore_permissions
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")

        if source.get("custom_sales_person"):
            target.append("sales_team", {
                "sales_person": source.custom_sales_person
            })
            
    def update_item(obj, target, source_parent):
        balance_qty = obj.qty - ordered_items.get(obj.item_code, 0.0)
        target.qty = balance_qty if balance_qty > 0 else 0
        target.stock_qty = flt(target.qty) * flt(obj.conversion_factor)

        if obj.against_blanket_order:
            target.against_blanket_order = obj.against_blanket_order
            target.blanket_order = obj.blanket_order
            target.blanket_order_rate = obj.blanket_order_rate

    def can_map_row(item) -> bool:
        """
        Row mapping from Quotation to Sales order:
        1. If no selections, map all non-alternative rows (that sum up to the grand total)
        2. If selections: Is Alternative Item/Has Alternative Item: Map if selected and adequate qty
        3. If selections: Simple row: Map if adequate qty
        """
        has_qty = item.qty > 0

        if not selected_rows:
            return not item.is_alternative

        if selected_rows and (item.is_alternative or item.has_alternative_item):
            return (item.name in selected_rows) and has_qty

        # Simple row
        return has_qty

    doclist = get_mapped_doc(
        "Quotation",
        source_name,
        {
            "Quotation": {"doctype": "Sales Order", "validation": {"docstatus": ["=", 1]}},
            "Quotation Item": {
                "doctype": "Sales Order Item",
                "field_map": {"parent": "prevdoc_docname", "name": "quotation_item"},
                "postprocess": update_item,
                "condition": can_map_row,
            },
            "Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "reset_value": True},
            "Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
            "Payment Schedule": {"doctype": "Payment Schedule", "add_if_empty": True},
        },
        target_doc,
        set_missing_values,
        ignore_permissions=ignore_permissions,
    )

    return doclist

# custom untuk menambahkan isi field custom_default_delivery_account dan custom_rabat_max
def get_basic_details(args, item, overwrite_warehouse=True):
	"""
	:param args: {
	                "item_code": "",
	                "warehouse": None,
	                "customer": "",
	                "conversion_rate": 1.0,
	                "selling_price_list": None,
	                "price_list_currency": None,
	                "price_list_uom_dependant": None,
	                "plc_conversion_rate": 1.0,
	                "doctype": "",
	                "name": "",
	                "supplier": None,
	                "transaction_date": None,
	                "conversion_rate": 1.0,
	                "buying_price_list": None,
	                "is_subcontracted": 0/1,
	                "ignore_pricing_rule": 0/1
	                "project": "",
	                barcode: "",
	                serial_no: "",
	                currency: "",
	                update_stock: "",
	                price_list: "",
	                company: "",
	                order_type: "",
	                is_pos: "",
	                project: "",
	                qty: "",
	                stock_qty: "",
	                conversion_factor: "",
	                against_blanket_order: 0/1
	        }
	:param item: `item_code` of Item object
	:return: frappe._dict
	"""

	if not item:
		item = frappe.get_doc("Item", args.get("item_code"))

	if item.variant_of and not item.taxes and frappe.db.exists("Item Tax", {"parent": item.variant_of}):
		item.update_template_tables()

	item_defaults = get_item_details.get_item_defaults(item.name, args.company)
	item_group_defaults = get_item_group_defaults(item.name, args.company)
	brand_defaults = get_brand_defaults(item.name, args.company)

	defaults = frappe._dict(
		{
			"item_defaults": item_defaults,
			"item_group_defaults": item_group_defaults,
			"brand_defaults": brand_defaults,
		}
	)

	warehouse = get_item_details.get_item_warehouse(item, args, overwrite_warehouse, defaults)

	if args.get("doctype") == "Material Request" and not args.get("material_request_type"):
		args["material_request_type"] = frappe.db.get_value(
			"Material Request", args.get("name"), "material_request_type", cache=True
		)

	expense_account = None

	if args.get("doctype") == "Purchase Invoice" and item.is_fixed_asset:
		from erpnext.assets.doctype.asset_category.asset_category import get_asset_category_account

		expense_account = get_asset_category_account(
			fieldname="fixed_asset_account", item=args.item_code, company=args.company
		)

	# Set the UOM to the Default Sales UOM or Default Purchase UOM if configured in the Item Master
	if not args.get("uom"):
		if args.get("doctype") in get_item_details.sales_doctypes:
			args.uom = item.sales_uom if item.sales_uom else item.stock_uom
		elif (args.get("doctype") in ["Purchase Order", "Purchase Receipt", "Purchase Invoice"]) or (
			args.get("doctype") == "Material Request" and args.get("material_request_type") == "Purchase"
		):
			args.uom = item.purchase_uom if item.purchase_uom else item.stock_uom
		else:
			args.uom = item.stock_uom

	# Set stock UOM in args, so that it can be used while fetching item price
	args.stock_uom = item.stock_uom

	if args.get("batch_no") and item.name != frappe.get_cached_value("Batch", args.get("batch_no"), "item"):
		args["batch_no"] = ""

	out = frappe._dict(
		{
			"item_code": item.name,
			"item_name": item.item_name,
			"description": cstr(item.description).strip(),
			"image": cstr(item.image).strip(),
			"warehouse": warehouse,
			"income_account": get_item_details.get_default_income_account(
				args, item_defaults, item_group_defaults, brand_defaults
			),
			"expense_account": expense_account
			or get_item_details.get_default_expense_account(args, item_defaults, item_group_defaults, brand_defaults),
			"discount_account": get_item_details.get_default_discount_account(
				args, item_defaults, item_group_defaults, brand_defaults
			),
			"custom_delivery_account": None,
			"provisional_expense_account": get_item_details.get_provisional_account(
				args, item_defaults, item_group_defaults, brand_defaults
			),
			"cost_center": get_item_details.get_default_cost_center(args, item_defaults, item_group_defaults, brand_defaults),
			"has_serial_no": item.has_serial_no,
			"has_batch_no": item.has_batch_no,
			"batch_no": args.get("batch_no"),
			"uom": args.uom,
			"stock_uom": item.stock_uom,
			"min_order_qty": flt(item.min_order_qty) if args.doctype == "Material Request" else "",
			"qty": flt(args.qty) or 1.0,
			"stock_qty": flt(args.qty) or 1.0,
			"price_list_rate": 0.0,
			"base_price_list_rate": 0.0,
			"rate": 0.0,
			"base_rate": 0.0,
			"amount": 0.0,
			"base_amount": 0.0,
			"net_rate": 0.0,
			"net_amount": 0.0,
			"discount_percentage": 0.0,
			"discount_amount": flt(args.discount_amount) or 0.0,
			"rebate_max": flt(item.get("custom_rabat_max")),
			"rebate_fix": flt(item.get("custom_cb")),
			"custom_rabat_max": flt(item.get("custom_rabat_max")),
			"update_stock": args.get("update_stock")
			if args.get("doctype") in ["Sales Invoice", "Purchase Invoice"]
			else 0,
			"delivered_by_supplier": item.delivered_by_supplier
			if args.get("doctype") in ["Sales Order", "Sales Invoice"]
			else 0,
			"is_fixed_asset": item.is_fixed_asset,
			"last_purchase_rate": item.last_purchase_rate if args.get("doctype") in ["Purchase Order"] else 0,
			"transaction_date": args.get("transaction_date"),
			"against_blanket_order": args.get("against_blanket_order"),
			"bom_no": item.get("default_bom"),
			"weight_per_unit": args.get("weight_per_unit") or item.get("weight_per_unit"),
			"weight_uom": args.get("weight_uom") or item.get("weight_uom"),
			"grant_commission": item.get("grant_commission"),
		}
	)

	default_supplier = get_item_details.get_default_supplier(args, item_defaults, item_group_defaults, brand_defaults)
	if default_supplier:
		out.supplier = default_supplier

	if item.get("enable_deferred_revenue") or item.get("enable_deferred_expense"):
		out.update(get_item_details.calculate_service_end_date(args, item))

	# calculate conversion factor
	if item.stock_uom == args.uom:
		out.conversion_factor = 1.0
	else:
		out.conversion_factor = args.conversion_factor or get_item_details.get_conversion_factor(item.name, args.uom).get(
			"conversion_factor"
		)

	args.conversion_factor = out.conversion_factor
	out.stock_qty = out.qty * out.conversion_factor
	args.stock_qty = out.stock_qty

	# calculate last purchase rate
	if args.get("doctype") in get_item_details.purchase_doctypes and not frappe.db.get_single_value(
		"Buying Settings", "disable_last_purchase_rate"
	):
		from erpnext.buying.doctype.purchase_order.purchase_order import item_last_purchase_rate

		out.last_purchase_rate = item_last_purchase_rate(
			args.name, args.conversion_rate, item.name, out.conversion_factor
		)

	# if default specified in item is for another company, fetch from company
	for d in [
		["Account", "income_account", "default_income_account"],
		["Account", "expense_account", "default_expense_account"],
		["Account", "custom_delivery_account", "custom_default_delivery_account"],
		["Cost Center", "cost_center", "cost_center"],
		["Warehouse", "warehouse", ""],
	]:
		if not out[d[1]]:
			out[d[1]] = frappe.get_cached_value("Company", args.company, d[2]) if d[2] else None

	for fieldname in ("item_name", "item_group", "brand", "stock_uom"):
		out[fieldname] = item.get(fieldname)

	if args.get("manufacturer"):
		part_no = get_item_manufacturer_part_no(args.get("item_code"), args.get("manufacturer"))
		if part_no:
			out["manufacturer_part_no"] = part_no
		else:
			out["manufacturer_part_no"] = None
			out["manufacturer"] = None
	else:
		data = frappe.get_value(
			"Item", item.name, ["default_item_manufacturer", "default_manufacturer_part_no"], as_dict=1
		)

		if data:
			out.update(
				{
					"manufacturer": data.default_item_manufacturer,
					"manufacturer_part_no": data.default_manufacturer_part_no,
				}
			)

	child_doctype = args.doctype + " Item"
	meta = frappe.get_meta(child_doctype)
	if meta.get_field("barcode"):
		get_item_details.update_barcode_value(out)

	if out.get("weight_per_unit"):
		out["total_weight"] = out.weight_per_unit * out.stock_qty

	return out

# update untuk menambahkan field fund source
def _get_party_details(
	party=None,
	account=None,
	party_type="Customer",
	company=None,
	posting_date=None,
	bill_date=None,
	price_list=None,
	currency=None,
	doctype=None,
	ignore_permissions=False,
	fetch_payment_terms_template=True,
	party_address=None,
	company_address=None,
	shipping_address=None,
	pos_profile=None,
):
	from erpnext import get_company_currency

	def set_account_and_due_date(party, account, party_type, company, posting_date, bill_date, doctype):
		if doctype not in ["Pre Order", "POS Invoice", "Sales Invoice", "Purchase Invoice"]:
			# not an invoice
			return {party_type.lower(): party}

		if party:
			account = party_file.get_party_account(party_type, party, company)

		account_fieldname = "debit_to" if party_type == "Customer" else "credit_to"
		out = {
			party_type.lower(): party,
			account_fieldname: account,
			"due_date": party_file.get_due_date(posting_date, party_type, party, company, bill_date),
		}

		return out
	
	party_details = frappe._dict(
		set_account_and_due_date(party, account, party_type, company, posting_date, bill_date, doctype)
	)
	party = party_details[party_type.lower()]
	party = frappe.get_doc(party_type, party)

	if not ignore_permissions:
		ptype = "select" if frappe.only_has_select_perm(party_type) else "read"
		frappe.has_permission(party_type, ptype, party, throw=True)

	currency = party.get("default_currency") or currency or get_company_currency(company)

	party_address, shipping_address = party_file.set_address_details(
		party_details,
		party,
		party_type,
		doctype,
		company,
		party_address,
		company_address,
		shipping_address,
		ignore_permissions=ignore_permissions,
	)
	party_file.set_contact_details(party_details, party, party_type)
	party_file.set_other_values(party_details, party, party_type)
	party_file.set_price_list(party_details, party, party_type, price_list, pos_profile)
	if party_type == "Customer":
		party_details["fund_source"] = "" if doctype == "Quotation" else party.get("custom_customer_fund_group")
		# party_details.update({
		# 	"fund_source": ,
		# 	"has_relation": 0,
		# 	"apply_rebate": frappe.get_cached_value("Customer Fund Source", party.custom_customer_fund_group, "apply_rebate") \
		# 		if party.get("custom_customer_fund_group") else 0,
		# 	"additional_rebate_disc": 0
		# })

		if party.get("custom_jenis_relasi"):
			jr = frappe.get_value("Jenis Relasi", party.get("custom_jenis_relasi"), ["has_relation", "customer_group", "additional_rebate_disc"], as_dict=1)

			party_details.update({
				"has_relation": jr.has_relation,
				"relasi_group": jr.customer_group,
				"additional_rebate_disc": jr.additional_rebate_disc or 0
			})

		# menghapus isi relasi atau shipping address
		if not party_details.get("has_relation"):
			party_details["relasi"] = ""
		else:
			party_details.__delattr__("shipping_address_name")
			party_details.__delattr__("shipping_address")

		# party_details.update(get_price_list_fund(company, party.name, party.get("custom_customer_fund_group")))

	tax_template = party_file.set_taxes(
		party.name,
		party_type,
		posting_date,
		company,
		customer_group=party_details.customer_group,
		supplier_group=party_details.supplier_group,
		tax_category=party_details.tax_category,
		billing_address=party_address,
		shipping_address=shipping_address,
	)

	if tax_template:
		party_details["taxes_and_charges"] = tax_template

	if frappe.cint(fetch_payment_terms_template):
		party_details["payment_terms_template"] = party_file.get_payment_terms_template(party.name, party_type, company)

	if not party_details.get("currency"):
		party_details["currency"] = currency

	# sales team
	if party_type == "Customer":
		party_details["sales_team"] = [
			{
				"sales_person": d.sales_person,
				"allocated_percentage": d.allocated_percentage or None,
				"commission_rate": d.commission_rate,
			}
			for d in party.get("sales_team")
		]

	# supplier tax withholding category
	if party_type == "Supplier" and party:
		party_details["supplier_tds"] = frappe.get_value(party_type, party.name, "tax_withholding_category")

	if not party_details.get("tax_category") and pos_profile:
		party_details["tax_category"] = frappe.get_value("POS Profile", pos_profile, "tax_category")

	return party_details


get_item_details.get_basic_details = get_basic_details
quotation._make_sales_order = _make_sales_order
party_file._get_party_details = _get_party_details