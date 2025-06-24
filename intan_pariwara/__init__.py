__version__ = "1.0.0"


import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cint, cstr, getdate, nowdate
from frappe.utils.data import flt

from erpnext import get_company_currency, get_default_company
from erpnext.accounts import (
	party as party_file,
	utils as acc_utils
)
from erpnext.selling.doctype.quotation import quotation

from erpnext.controllers.status_updater import StatusUpdater

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
	party_details = frappe._dict(
		party_file.set_account_and_due_date(party, account, party_type, company, posting_date, bill_date, doctype)
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

	if cint(fetch_payment_terms_template):
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

# fix parent percent jika link kosong
def _update_percent_field_in_targets(self, args, update_modified=True):
	"""Update percent field in parent transaction"""
	if args.get("percent_join_field_parent"):
		# if reference to target doc where % is to be updated, is
		# in source doc's parent form, consider percent_join_field_parent
		args["name"] = self.get(args["percent_join_field_parent"])
		if args["name"]:
			self._update_percent_field(args, update_modified)
	else:
		distinct_transactions = set(
			d.get(args["percent_join_field"]) for d in self.get_all_children(args["source_dt"])
		)

		for name in distinct_transactions:
			if name:
				args["name"] = name
				self._update_percent_field(args, update_modified)

# tambahan account untuk uang muka untuk document dari sales order
def update_reference_in_payment_entry(
	d, payment_entry, do_not_save=False, skip_ref_details_update_for_pe=False, dimensions_dict=None
):
	reference_details = {
		"reference_doctype": d.against_voucher_type,
		"reference_name": d.against_voucher,
		"total_amount": d.grand_total,
		"outstanding_amount": d.outstanding_amount,
		"allocated_amount": d.allocated_amount,
		"exchange_rate": d.exchange_rate
		if d.difference_amount is not None
		else payment_entry.get_exchange_rate(),
		"exchange_gain_loss": d.difference_amount,
		"account": d.account,
		"dimensions": d.dimensions,
	}
	update_advance_paid = []

	# Update Reconciliation effect date in reference
	if payment_entry.book_advance_payments_in_separate_party_account:
		if payment_entry.advance_reconciliation_takes_effect_on == "Advance Payment Date":
			reconcile_on = payment_entry.posting_date
		elif payment_entry.advance_reconciliation_takes_effect_on == "Oldest Of Invoice Or Advance":
			date_field = "posting_date"
			if d.against_voucher_type in ["Sales Order", "Purchase Order"]:
				date_field = "transaction_date"
			reconcile_on = frappe.db.get_value(d.against_voucher_type, d.against_voucher, date_field)

			if getdate(reconcile_on) < getdate(payment_entry.posting_date):
				reconcile_on = payment_entry.posting_date
		elif payment_entry.advance_reconciliation_takes_effect_on == "Reconciliation Date":
			reconcile_on = nowdate()

		reference_details.update({"reconcile_effect_on": reconcile_on})

	if d.voucher_detail_no:
		existing_row = payment_entry.get("references", {"name": d["voucher_detail_no"]})[0]

		# Update Advance Paid in SO/PO since they are getting unlinked
		if existing_row.get("reference_doctype") in ["Sales Order", "Purchase Order"]:
			update_advance_paid.append((existing_row.reference_doctype, existing_row.reference_name))

		if d.allocated_amount <= existing_row.allocated_amount:
			existing_row.allocated_amount -= d.allocated_amount

			new_row = payment_entry.append("references")
			new_row.docstatus = 1
			for field in list(reference_details):
				new_row.set(field, reference_details[field])

			new_row.update({
				"account_from": existing_row.account_from,
				"order_type": existing_row.reference_doctype,
				"order_from": existing_row.reference_name,
			})

			row = new_row
	else:
		new_row = payment_entry.append("references")
		new_row.docstatus = 1
		new_row.update(reference_details)
		row = new_row

	payment_entry.flags.ignore_validate_update_after_submit = True
	payment_entry.clear_unallocated_reference_document_rows()
	payment_entry.setup_party_account_field()
	payment_entry.set_missing_values()
	if not skip_ref_details_update_for_pe:
		reference_exchange_details = frappe._dict()
		if d.against_voucher_type == "Journal Entry" and d.exchange_rate:
			reference_exchange_details.update(
				{
					"reference_doctype": d.against_voucher_type,
					"reference_name": d.against_voucher,
					"exchange_rate": d.exchange_rate,
				}
			)
		payment_entry.set_missing_ref_details(
			update_ref_details_only_for=[(d.against_voucher_type, d.against_voucher)],
			reference_exchange_details=reference_exchange_details,
		)
	payment_entry.set_amounts()
	payment_entry.make_exchange_gain_loss_journal(
		frappe._dict({"difference_posting_date": d.difference_posting_date}), dimensions_dict
	)

	# Ledgers will be reposted by Reconciliation tool
	payment_entry.flags.ignore_reposting_on_reconciliation = True
	if not do_not_save:
		payment_entry.save(ignore_permissions=True)
	return row, update_advance_paid

quotation._make_sales_order = _make_sales_order
party_file._get_party_details = _get_party_details
acc_utils.update_reference_in_payment_entry = update_reference_in_payment_entry
StatusUpdater._update_percent_field_in_targets = _update_percent_field_in_targets