# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from erpnext.stock.utils import _update_item_info
from frappe.query_builder.custom import ConstantColumn

BarcodeScanResult = dict[str, str | None]

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