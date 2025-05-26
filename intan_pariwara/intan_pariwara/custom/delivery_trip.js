// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Delivery Trip", {
    refresh: function (frm) {
        frm.remove_custom_button("Delivery Note")

        if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Delivery Note"),
				() => {
					erpnext.utils.map_current_doc({
						method: "erpnext.stock.doctype.delivery_note.delivery_note.make_delivery_trip",
						source_doctype: "Delivery Note",
						target: frm,
						date_field: "posting_date",
						setters: {
							company: frm.doc.company,
							customer: null,
						},
						get_query_filters: {
							docstatus: 1,
							delivery_trip_used: 0,
							company: frm.doc.company,
							status: ["Not In", ["Completed", "Cancelled"]],
						},
					});
				},
				__("Get stops from")
			);
		}
    },
})