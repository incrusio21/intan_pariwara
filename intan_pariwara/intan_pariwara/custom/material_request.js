// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
        if (frm.doc.docstatus == 1 && frm.doc.status != "Stopped" 
            && frm.doc.material_request_type === "Material Transfer"
            && flt(frm.doc.per_packing, precision) < 100) {
                frm.add_custom_button(
                    __("Packing List"),
                    () => {
                        frappe.model.open_mapped_doc({
                            method: "intan_pariwara.intan_pariwara.custom.material_request.make_packing_list",
                            frm: frm,
                        });
                    },
                    __("Create")
                );
        }

        frm.remove_custom_button(__("Material Transfer"), __("Create"))
        frm.remove_custom_button(__("Material Transfer (In Transit)"), __("Create"))
    }
})