// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customer', {
	custom_kab_kota(frm) {
        if(!frm.doc.custom_kab_kota) return

        frappe.call({
            method: "intan_pariwara.intan_pariwara.custom.customer.get_price_list",
            args:{
                teritory: frm.doc.custom_kab_kota
            },
            callback: function (r) {
                if (r.message) {
                    frappe.run_serially([
                        () => frm.set_value(r.message),
                        () => frm.refresh()
                    ]);
                }
            }
        })
    }
})