# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

from erpnext.controllers.accounts_controller import merge_taxes
from erpnext.stock.doctype.delivery_note.delivery_note import get_invoiced_qty_map, get_returned_qty_map
import frappe
from frappe import _
from erpnext.stock.utils import _update_item_info
from frappe.model.mapper import get_mapped_doc
from frappe.query_builder.custom import ConstantColumn
from frappe.utils import flt

BarcodeScanResult = dict[str, str | None]

def set_order_tax_template(self, method=None):
    item_with_order = self.get("items", {"purchase_order": True})
    if not item_with_order:
        return
    
    self.taxes_and_charges = frappe.get_value("Purchase Order", item_with_order[0].purchase_order, "taxes_and_charges")

def validate_duplicate_qr(self, method=None):
    from intan_pariwara.utils.qr_code import get_qr_code_nos

    for d in self.items:
        if not d.get("qr_code_no"):
            continue
        
        for qr_name in get_qr_code_nos(d.qr_code_no):
            qr_code_status(qr_name, d.name)

@frappe.whitelist()
def scan_qr_barcode(search_value: str) -> BarcodeScanResult:
    def set_cache(data: BarcodeScanResult):
        frappe.cache().set_value(f"intan_pariwara:barcode_scan:{search_value}", data, expires_in_sec=120)

    def get_cache() -> BarcodeScanResult | None:
        if data := frappe.cache().get_value(f"intan_pariwara:barcode_scan:{search_value}"):
            return data

    if scan_data := get_cache():
        return scan_data
    
    parts = search_value.split(";")
    if len(parts) > 6:
        qr_code_no = ";".join(parts[2:])
        if not qr_code_status(qr_code_no):
            return {}
        
        qr_item = frappe.qb.DocType("Purchase Order Item")
        item_qr_list = (
            frappe.qb.from_(qr_item)
            .select(
                ConstantColumn(qr_code_no).as_("qr_code_no"),
                qr_item.parent.as_("document_name"),
                qr_item.item_code,
                qr_item.name.as_("document_detail"),
                qr_item.stock_uom.as_("uom"),
                ConstantColumn(parts[4]).as_("qty"),
            )
            .where(
                (qr_item.item_code == parts[2]) 
                & (qr_item.parent == parts[3])
                & (qr_item.received_qty < qr_item.qty)
            )
        ).run(as_dict=True)

        if item_qr_list:
            return item_qr_list 

    # search barcode no
    barcode_data = frappe.db.get_value(
        "Item Barcode",
        {"barcode": search_value},
        ["barcode", "parent as item_code", "uom"],
        as_dict=True,
    )
    if barcode_data:
        _update_item_info(barcode_data)
        set_cache(barcode_data)
        return barcode_data

    # search serial no
    serial_no_data = frappe.db.get_value(
        "Serial No",
        search_value,
        ["name as serial_no", "item_code", "batch_no"],
        as_dict=True,
    )
    if serial_no_data:
        _update_item_info(serial_no_data)
        set_cache(serial_no_data)
        return serial_no_data

    # search batch no
    batch_no_data = frappe.db.get_value(
        "Batch",
        search_value,
        ["name as batch_no", "item as item_code"],
        as_dict=True,
    )
    if batch_no_data:
        if frappe.get_cached_value("Item", batch_no_data.item_code, "has_serial_no"):
            frappe.throw(
                _(
                    "Batch No {0} is linked with Item {1} which has serial no. Please scan serial no instead."
                ).format(search_value, batch_no_data.item_code)
            )

        _update_item_info(batch_no_data)
        set_cache(batch_no_data)
        return batch_no_data

    return {}

def qr_code_status(qr_code, child_name=None):
    doctype = frappe.qb.DocType("Purchase Receipt Item")

    query = (
        frappe.qb.from_(doctype)
        .select(
            doctype.parent
        ).where(
            (doctype.docstatus == 1)
            & (
                (doctype.qr_code_no == qr_code) |
                (doctype.qr_code_no.like(qr_code + "\n%")) |
                (doctype.qr_code_no.like("%\n" + qr_code + "\n%")) |
                (doctype.qr_code_no.like("%\n" + qr_code))
            )
        )
        .groupby(doctype.parent)
    )
    
    if child_name:
        query = query.where((doctype.name != child_name))
        
    qr_code_used = query.run()
    if qr_code_used:
        frappe.throw("QR code can only be used once")

    return True
           
@frappe.whitelist()
def detail_item_order(item, set_warehouse=None):
	ress = {}
	fields = ["price_list_rate", "rate", "discount_percentage"]
	if not set_warehouse:
		fields.append("warehouse")

	ress.update(
		frappe.get_value("Purchase Order Item", {"name": item}, fields, as_dict=1)
	)
	return ress

@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, args=None):
    from erpnext.accounts.party import get_payment_terms_template

    doc = frappe.get_doc("Purchase Receipt", source_name)
    returned_qty_map = get_returned_qty_map(source_name)
    invoiced_qty_map = get_invoiced_qty_map(source_name)

    def set_missing_values(source, target):
        if len(target.get("items")) == 0:
            frappe.throw(_("All items have already been Invoiced/Returned"))

        doc = frappe.get_doc(target)
        doc.payment_terms_template = get_payment_terms_template(source.supplier, "Supplier", source.company)
        doc.run_method("onload")
        doc.run_method("set_missing_values")

        if args and args.get("merge_taxes"):
            merge_taxes(source.get("taxes") or [], doc)

        doc.run_method("set_other_charges")
        doc.run_method("calculate_taxes_and_totals")
        doc.set_payment_schedule()

    def update_item(source_doc, target_doc, source_parent):
        target_doc.qty, returned_qty = get_pending_qty(source_doc)
        if frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice"):
            target_doc.rejected_qty = 0
        target_doc.stock_qty = flt(target_doc.qty) * flt(
            target_doc.conversion_factor, target_doc.precision("conversion_factor")
        )
        returned_qty_map[source_doc.name] = returned_qty

    def get_pending_qty(item_row):
        qty = item_row.qty
        if frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice"):
            qty = item_row.received_qty

        pending_qty = qty - invoiced_qty_map.get(item_row.name, 0)

        if frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice"):
            return pending_qty, 0

        returned_qty = flt(returned_qty_map.get(item_row.name, 0))
        if item_row.rejected_qty and returned_qty:
            returned_qty -= item_row.rejected_qty

        if returned_qty:
            if returned_qty >= pending_qty:
                pending_qty = 0
                returned_qty -= pending_qty
            else:
                pending_qty -= returned_qty
                returned_qty = 0

        return pending_qty, returned_qty

    doclist = get_mapped_doc(
        "Purchase Receipt",
        source_name,
        {
            "Purchase Receipt": {
                "doctype": "Purchase Invoice",
                "field_map": {
                    "supplier_warehouse": "supplier_warehouse",
                    "is_return": "is_return",
                    "bill_date": "bill_date",
                },
                "validation": {
                    "docstatus": ["=", 1],
                },
            },
            "Purchase Receipt Item": {
                "doctype": "Purchase Invoice Item",
                "field_map": {
                    "name": "pr_detail",
                    "parent": "purchase_receipt",
                    "qty": "received_qty",
                    "purchase_order_item": "po_detail",
                    "purchase_order": "purchase_order",
                    "is_fixed_asset": "is_fixed_asset",
                    "asset_location": "asset_location",
                    "asset_category": "asset_category",
                    "wip_composite_asset": "wip_composite_asset",
                },
                "postprocess": update_item,
                "filter": lambda d: get_pending_qty(d)[0] <= 0
                if not doc.get("is_return")
                else get_pending_qty(d)[0] > 0,
            },
            "Purchase Taxes and Charges": {
                "doctype": "Purchase Taxes and Charges",
                "reset_value": not (args and args.get("merge_taxes")),
                "ignore": args.get("merge_taxes") if args else 0,
            },
        },
        target_doc,
        set_missing_values,
    )

    return doclist