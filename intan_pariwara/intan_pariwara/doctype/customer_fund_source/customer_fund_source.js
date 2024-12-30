// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer Fund Source", {
	refresh(frm) {
        $.each(["rebate_order_account", "rebate_additional_account", "rebate_payable_account", "rebate_additional_payable_account"], function(i, field){
            frm.set_query(field, "account_details", function(doc, cdt, cdn){
                let item = locals[cdt][cdn]
                if(!item.company){
                    frappe.throw("Please Select Company First")
                }
                
                return {
                    filters:{
                        company: item.company,
                        is_group: 0
                    }
                }
            })
        })
	},
});
