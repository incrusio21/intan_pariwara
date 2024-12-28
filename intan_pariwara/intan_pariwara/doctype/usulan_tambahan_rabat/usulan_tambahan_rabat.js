// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Usulan Tambahan Rabat", {
    setup(frm) {
        if(!(frm.doc.rebate_account_from && frm.doc.rebate_account_to)){
            frm.trigger("get_rebate_account")
        }
    },
	refresh(frm) {
        frm.set_query("sales_order", function (doc) {
			return {
				filters: {
					docstatus: 1,
					fund_source: ["is", "set"],
				},
			};
		})
	},
    rebate(frm) {
        if(!frm.doc.sales_order){
            frappe.throw("Select Sales Order first")
        }

        frm.set_value("rebate_total", flt(frm.doc.rebate / 100 * frm.doc.sales_order_total))
    },
    company(frm){
        frm.trigger("get_rebate_account")
    },
    get_rebate_account(frm){
        if(!frm.doc.company){
            frappe.throw("Please Select Company First")
        }

        frappe.call({
            method: "intan_pariwara.controllers.queries.additional_rebate_account",
            args: {
                company: frm.doc.company,
                rebate_from: frm.doc.rebate_account_from,
                rebate_to: frm.doc.rebate_account_to,
            },
            callback: function (r) {
                if (r.message) {
                    frappe.run_serially([
                        () => frm.set_value(r.message)
                    ]);
                }
            },
        });
    }
});
