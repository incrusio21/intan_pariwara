// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rebate Ledger Entry", {
	refresh(frm) {
		frm.page.btn_secondary.hide();
	},
});
