// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stock Entry Detail", {
    material_request_item: function (frm, cdt, cdn) {
        var item = locals[cdt][cdn]
        
        frappe.call({
            method: "intan_pariwara.intan_pariwara.custom.stock_entry.detail_item_request",
            args:{
                from_warehouse: frm.doc.from_warehouse,
                to_warehouse: frm.doc.to_warehouse,
                item: item.material_request_item
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

cur_frm.cscript.scan_barcode = function(){
    frappe.flags.dialog_set = false;
    var opts = {}
    if(!this.frm.doc.outgoing_stock_entry){
        opts = { document_name_field: "material_request", document_detail_field: "material_request_item" }
    }else{
        opts = { 
            scan_api: "intan_pariwara.intan_pariwara.custom.stock_entry.scan_qr_barcode",
            document_name_field: "against_stock_entry", document_detail_field: "ste_detail",
            args: {
                material_transfer: this.frm.doc.outgoing_stock_entry
            }
        }
    }

    const barcode_scanner = new intan_pariwara.utils.BarcodeScanner({
        frm: this.frm, 
        purpose: this.frm.doc.stock_entry_type, 
        ...opts
    });

    barcode_scanner.process_scan();
}