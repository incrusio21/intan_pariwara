// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.ui.form.off("Pick List", "material_request")
frappe.ui.form.off("Pick List", "add_get_items_button")
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
    },
	material_request: (frm) => {
		frm.clear_table("locations")
		
		erpnext.utils.map_current_doc({
			method: "erpnext.stock.doctype.material_request.material_request.create_pick_list",
			target: frm,
			source_name: frm.doc.material_request,
		});
	},
	add_get_items_button: (frm) => {
		let purpose = frm.doc.purpose;
		if (purpose != "Delivery" || frm.doc.docstatus !== 0) {
			frm.remove_custom_button(__("Get Items"))
			return
		};
		let get_query_filters = {
			docstatus: 1,
			per_delivered: ["<", 100],
			status: ["!=", ""],
			customer: frm.doc.customer,
		};
		frm.get_items_btn = frm.add_custom_button(__("Get Items"), () => {
			erpnext.utils.map_current_doc({
				method: "erpnext.selling.doctype.sales_order.sales_order.create_pick_list",
				source_doctype: "Sales Order",
				target: frm,
				setters: {
					company: frm.doc.company,
					customer: frm.doc.customer,
				},
				date_field: "transaction_date",
				get_query_filters: get_query_filters,
			});
		});
	}
})