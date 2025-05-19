// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
intan_pariwara.sales_common.setup_selling_controller(erpnext.selling.QuotationController)

frappe.ui.form.on("Quotation", {
    discount_percent(frm) {
		frm.doc.items.forEach((item) => {
			frappe.model.set_value(item.doctype, item.name, "discount_percentage", frm.doc.discount_percent || 0)
		});
	}
})

intan_pariwara.selling.QuotationController = class QuotationController extends intan_pariwara.selling.SellingController {
	party_name(doc) {
		var me = this;
        frappe.flags.trigger_from_customer = true
        erpnext.utils.get_party_details(this.frm, null, null, function () {
            if(me.frm.doc.quotation_to == "Customer"){
                me.get_price_list_fund(doc, true)
            }else{
                me.apply_price_list();
            }
        });

		if (me.frm.doc.quotation_to == "Lead" && me.frm.doc.party_name) {
			me.frm.trigger("get_lead_details");
		}
	}
}

cur_frm.script_manager.make(intan_pariwara.selling.QuotationController);
