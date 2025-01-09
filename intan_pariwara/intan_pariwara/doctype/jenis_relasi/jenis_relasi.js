// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Jenis Relasi", {
	refresh(frm) {
        frm.set_query("customer_group", function(doc){
            return {
                filters: {
                    is_group: 0
                },
            }
        })
	},
});
