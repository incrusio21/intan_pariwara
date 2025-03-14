# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from erpnext.stock.utils import _update_item_info

BarcodeScanResult = dict[str, str | None]

@frappe.whitelist()
def scan_qr_barcode(search_value: str) -> BarcodeScanResult:
    def set_cache(data: BarcodeScanResult):
        frappe.cache().set_value(f"intan_pariwara:barcode_scan:{search_value}", data, expires_in_sec=120)

    def get_cache() -> BarcodeScanResult | None:
        if data := frappe.cache().get_value(f"intan_pariwara:barcode_scan:{search_value}"):
            return data

    if scan_data := get_cache():
        return scan_data
    
    qr_bundle = frappe.db.get_value(
        "Qr Code Packing Bundle",
        {"data_qr": search_value},
        ["name", "packing_list", "packing_purpose", "packing_docname"],
        as_dict=True,
    )
    if qr_bundle:
        item_qr_list = frappe.get_all(
            "Qr Code Bundle Item", 
            filters={"parent": qr_bundle.name}, 
            fields=["item_code", "qty", "document_detail", "stock_uom as uom"]
        )
        set_cache(item_qr_list)
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