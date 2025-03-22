// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.ui.form.on("Pick List", {
    refresh: function (frm) {
        if (frm.doc.docstatus == 1) {
			if (
				frm.doc.status !== "Completed" &&
				flt(frm.doc.per_packing) < 100
			) {
				if (frappe.model.can_create("Packing List")) {
					frm.add_custom_button(
						__("Packing List"),
						() => {
							frappe.model.open_mapped_doc({
								method: "intan_pariwara.intan_pariwara.custom.pick_list.make_packing_list",
								frm: frm,
								freeze: true,
								freeze_message: __("Creating Packing List ..."),
							});
						},
						__("Create")
					);
				}
			}
		}

		frm.remove_custom_button(__("Delivery Note"), __("Create"));
		frm.remove_custom_button(__("Stock Entry"),__("Create"));
    }
})