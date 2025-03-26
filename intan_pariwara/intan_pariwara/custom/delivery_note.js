// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt
frappe.provide("intan_pariwara.stock")

intan_pariwara.sales_common.setup_selling_controller(erpnext.stock.DeliveryNoteController)

frappe.ui.form.on("Delivery Note", {
    refresh: function (frm) {
        // new intan_pariwara.utils.OtpVerified({frm});
    },
})

frappe.ui.form.on("Delivery Note Item", {
    so_detail: function (frm, cdt, cdn) {
        var item = locals[cdt][cdn]
        
        frappe.call({
            method: "intan_pariwara.intan_pariwara.custom.delivery_note.detail_item_order",
            args:{
                set_warehouse: frm.doc.set_warehouse,
                item: item.so_detail
            },
            callback: function (r) {
                if (r.message) {
                    frappe.run_serially([
                        () => frappe.model.set_value(item.doctype, item.name, r.message),
                        () => frm.refresh_fields("items")
                    ]);
                }
            }
        })
    },
})

intan_pariwara.stock.DeliveryNoteController = class DeliveryNoteController extends intan_pariwara.selling.SellingController {
	refresh(doc, dt, dn) {
        var me = this;

		super.refresh(doc, dt, dn);
        
        this.frm.remove_custom_button(__("Sales Return"), __("Create"));

        if (doc.docstatus == 1 
            && flt(doc.per_return_request, 2) < 100
            && frappe.model.can_create("Sales Return Request")) {
            this.frm.add_custom_button(
                __("Sales Return Request"),
                function () {
                    frappe.model.open_mapped_doc({
                        method: "intan_pariwara.intan_pariwara.custom.delivery_note.make_sales_return_req",
                        frm: me.frm,
                        freeze: true,
                        freeze_message: __("Creating Sales Return Request ..."),
                    });
                },
                __("Create")
            );
        }
    }

    scan_barcode() {
		frappe.flags.dialog_set = false;
		const barcode_scanner = new intan_pariwara.utils.BarcodeScanner({frm:this.frm, purpose: "Delivery"});
		barcode_scanner.process_scan();
	}
}

cur_frm.script_manager.make(intan_pariwara.stock.DeliveryNoteController);