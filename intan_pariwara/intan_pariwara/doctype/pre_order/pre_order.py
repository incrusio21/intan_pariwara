# Copyright (c) 2024, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate
from frappe.utils.csvutils import getlink

from erpnext.controllers.selling_controller import SellingController

from intan_pariwara.controllers.account_controller import AccountsController

class PreOrder(AccountsController, SellingController):
	
	def validate(self):
		super().validate()
		self.validate_expected_date()
		self.validate_items()
		self.validate_items()
		self.get_receivable_amount()
		self.set_status()
		self.validate_uom_is_integer("stock_uom", "stock_qty")
		self.validate_uom_is_integer("uom", "qty")
		self.set_child_wharehouse()
		self.set_customer_mobile_no()

		if self.items:
			self.with_items = 1

		from erpnext.stock.doctype.packed_item.packed_item import make_packing_list

		make_packing_list(self)
	
	def set_customer_mobile_no(self):
		if self.contact_person:
			return
		
		self.contact_mobile = frappe.get_cached_value("Customer", self.customer, "mobile_no")

	def validate_expected_date(self):
		date = getdate(self.transaction_date)
		if date > getdate(self.delivery_date) or date > getdate(self.payment_date):
			frappe.throw("Transaction date must be on or before Expected Delivery Date and Payment Date.")

	def validate_items(self):
		tax_type = set()
		for d in self.items:
			item = frappe.get_cached_value("Item", d.item_code, ["custom_tax_type", "custom_produk_inti", "produk_inti_type"], as_dict=1)
			tax_type.add(item.custom_tax_type)
			if len(tax_type) > 1:
				frappe.throw("Multiple Tax Types are present among Items.")

			if self.produk_inti_type and self.produk_inti_type != item.produk_inti_type:
				frappe.throw("Transaction is limited to Produk Inti {} only".format(self.produk_inti_type))

	def get_receivable_amount(self):
		if not self.get("__is_local"):
			return

		receivable_amount = frappe.db.sql("""
			select sum(amount_in_account_currency) as amount
			from `tabPayment Ledger Entry` ple 
			where 
				ple.docstatus < 2 and ple.delinked = 0 and ple.party_type=%(party_type)s and ple.party=%(party)s
				and ple.posting_date <= %(to_date)s and ple.account_type = "Receivable" and account = %(account)s
		""", {
			"to_date": self.transaction_date,
			"party_type": "Customer",
			"party": self.customer,
			"account": self.debit_to,
		})

		self.receivable_amount = receivable_amount[0][0] if receivable_amount else 0

	def set_child_wharehouse(self):
		if not self.set_warehouse:
			return
		
		for d in self.items:
			d.warehouse = self.set_warehouse
		
	def on_submit(self):
		# Check for Approving Authority
		frappe.get_doc("Authorization Control").validate_approving_authority(
			self.doctype, self.company, self.base_grand_total, self
		)

		if self.fund_source == "Dana Siswa":
			make_sales_order(self.name, submit=True)
			
		# update enquiry status
		# self.update_opportunity("Quotation")
		# self.update_lead()

	def on_cancel(self):
		if self.lost_reasons:
			self.lost_reasons = []
		super().on_cancel()

		# update enquiry status
		self.set_status(update=True)
		# self.update_opportunity("Open")
		# self.update_lead()

	@frappe.whitelist()
	def otp_verification(self, otp):
		if self.otp_verified:
			return
		
		from intan_pariwara.controllers.otp_notification import get_verification_otp
		if get_verification_otp(str(otp), self.name):
			self.db_set("otp_verified", 1)

@frappe.whitelist()
def make_sales_order(source_name: str, target_doc=None, submit=False):
	# if not frappe.db.get_singles_value(
	# 	"Selling Settings", "allow_sales_order_creation_for_expired_quotation"
	# ):
	# 	quotation = frappe.db.get_value(
	# 		"Quotation", source_name, ["transaction_date", "valid_till"], as_dict=1
	# 	)
	# 	if quotation.valid_till and (
	# 		quotation.valid_till < quotation.transaction_date or quotation.valid_till < getdate(nowdate())
	# 	):
	# 		frappe.throw(_("Validity period of this quotation has ended."))
	sales_order_list = [] 
	for row in ["Tax", "Non Tax"]:
		doc = _make_sales_order(source_name, target_doc=None, item_type=row)
		if len(doc.items) > 0:
			doc.save()
			if submit:
				doc.submit()

			sales_order_list.append(doc.name)
	
	if not sales_order_list:
		frappe.throw("Can't make Sales Order")

	message = "List Sales Order :"
	for so in sales_order_list:
		message += "<br> {}".format(getlink("Sales Order", so))

	frappe.msgprint(message)

def _make_sales_order(source_name, target_doc=None, item_type="Non Tax", null_type_be="Non Tax"):
	def set_missing_values(source, target):
		if source.referral_sales_partner:
			target.sales_partner = source.referral_sales_partner
			target.commission_rate = frappe.get_value(
				"Sales Partner", source.referral_sales_partner, "commission_rate"
			)
		
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")
		if source.sales_person:
			target.append("sales_team", {
				"sales_person": source.sales_person,
				"allocated_percentage": 100,
			})

	def update_item(obj, target, source_parent):
		target.qty = obj.qty - obj.ordered_qty
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
		has_qty = item.qty > item.ordered_qty

		item_tax_type = frappe.get_cached_value("Item", item.item_code, "custom_tax_type")
		if not item_tax_type: 
			item_tax_type = null_type_be

		if item_tax_type != item_type:
			return False
		
		# if not selected_rows:
		# 	return not item.is_alternative

		# if selected_rows and (item.is_alternative or item.has_alternative_item):
		# 	return (item.name in selected_rows) and has_qty

		# Simple row
		return has_qty
	
	doclist = get_mapped_doc(
		"Pre Order",
		source_name,
		{
			"Pre Order": {
				"doctype": "Sales Order", 
				"validation": {"docstatus": ["=", 1]},
				"field_map": { 
					"transaction_date": "transaction_date",
					"delivery_date": "delivery_date",
					"payment_date": "payment_date"
				}
			},
			"Pre Order Item": {
				"doctype": "Sales Order Item",
				"field_map": {"parent": "custom_pre_order", "name": "custom_pre_order_item"},
				"postprocess": update_item,
				"condition": can_map_row,
			},
			"Sales Taxes and Charges": {"doctype": "Sales Taxes and Charges", "reset_value": True},
			"Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
			"Payment Schedule": {"doctype": "Payment Schedule", "add_if_empty": True},
		},
		target_doc,
		set_missing_values,
	)

	return doclist