// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("intan_pariwara.stock")

frappe.ui.form.on("Purchase Receipt Item", {
    purchase_order_item: function (frm, cdt, cdn) {
        var item = locals[cdt][cdn]
        
        frappe.call({
            method: "intan_pariwara.intan_pariwara.custom.purchase_receipt.detail_item_order",
            args:{
                set_warehouse: frm.doc.set_warehouse,
                item: item.purchase_order_item
            },
            callback: function (r) {
                if (r.message) {
                    frappe.run_serially([
                        () => frappe.model.set_value(item.doctype, item.name, r.message),
                        () => refresh_fields("items")
                    ]);
                }
            }
        })
    },
})

intan_pariwara.stock.PurchaseReceiptController = class PurchaseReceiptController extends erpnext.stock.PurchaseReceiptController {
    scan_barcode() {
		frappe.flags.dialog_set = false;
		const barcode_scanner = new intan_pariwara.utils.BarcodeScanner({
            frm: this.frm,
            scan_api: "intan_pariwara.intan_pariwara.custom.purchase_receipt.scan_qr_barcode",
            document_name_field: "purchase_order",
            document_detail_field: "purchase_order_item"
        });
		barcode_scanner.process_scan();
	}
}

cur_frm.script_manager.make(intan_pariwara.stock.PurchaseReceiptController);

// 2024-12-17;241217|YOSHC|S1;010101010U05PA;PUR-ORD-2025-00001;10