// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Delivery Trip", "refresh")
frappe.ui.form.on("Delivery Trip", {
    refresh: function (frm) {
		if (frm.doc.docstatus == 1 && frm.doc.delivery_stops.length > 0) {
			frm.add_custom_button(__("Notify Customers via Email"), function () {
				frm.trigger("notify_customers");
			});
		}

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Delivery Note"),
				() => {
					erpnext.utils.map_current_doc({
						method: "erpnext.stock.doctype.delivery_note.delivery_note.make_delivery_trip",
						source_doctype: "Delivery Note",
						target: frm,
						date_field: "posting_date",
						size:"extra-large",
						setters: [
							{
								fieldtype:"Link",
								label:__("Warehouse"),
								fieldname:"set_warehouse",
							},
							{
								fieldtype:"Small Text",
								label:__("Alamat"),
								fieldname:"address_display",
								hidden:1
							},
						],
						get_query_method: "intan_pariwara.intan_pariwara.custom.delivery_trip.dn_query",
						
					});
				},
				__("Get stops from")
			);
		}
		
		frm.add_custom_button(
			__("Delivery Notes"),
			function () {
				frappe.set_route("List", "Delivery Note", {
					name: [
						"in",
						frm.doc.delivery_stops.map((stop) => {
							return stop.delivery_note;
						}),
					],
				});
			},
			__("View")
		);
	}
})
