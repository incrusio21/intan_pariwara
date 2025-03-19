// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Master SIPLAH", {
	refresh(frm) {
		frm.set_query("account",function(){
			return {
				filters: {
					"company": "Intan Pariwara Vitarana"
				}
			}
		})
	},
});
