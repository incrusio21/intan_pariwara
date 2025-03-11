// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Return Request", {
	refresh(frm) {
        frm.set_query("delivery_note", function(doc){
            if(!doc.customer){
                frappe.throw("Please Set Customer First")
            }

            return {
                filters: {
                    is_return: 0,
                    docstatus: 1,
                    customer: doc.customer,
                    per_returned: ["<", 100]
                },
            }
        })

        frm.set_df_property("items", "cannot_add_rows", true);
	},
    delivery_note(frm){
        frm.set_value("items", null);

        if (frm.doc.delivery_note) {
            erpnext.utils.map_current_doc({
                method: "intan_pariwara.intan_pariwara.custom.delivery_note.make_sales_return_req",
                source_name: frm.doc.delivery_note,
                target_doc: frm,
                freeze: true,
                freeze_message: __("Creating Sales Return Request ..."),
            });
        }
    }
});

intan_pariwara.selling.ReturnSalesController = class ReturnSalesController {
    refresh(doc, dt, dn) {
        var me = this
        new intan_pariwara.utils.OtpVerified({frm: me.frm});

        if (doc.docstatus == 1 
            && flt(doc.per_returned, 2) < 100
            && frappe.model.can_create("Delivery Note")) {
            this.frm.add_custom_button(
                __("Sales Return"),
                function () {
                    frappe.model.open_mapped_doc({
                        method: "intan_pariwara.intan_pariwara.doctype.sales_return_request.sales_return_request.make_sales_return",
                        frm: me.frm,
                    });
                },
                __("Create")
            );
        }
    }

    qty(doc, dt, dn){
        let total_qty = 0
        doc.items.forEach((val) => {
            total_qty += val.qty
		})
        
        this.frm.set_value("total_qty", total_qty)
    }
}

cur_frm.script_manager.make(intan_pariwara.selling.ReturnSalesController);
