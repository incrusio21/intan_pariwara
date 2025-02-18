// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Packing List", {
	setup: (frm) => {
		frm.set_query("sales_order", () => {
			return {
				filters: {
					docstatus: 1,
					per_packing: ["<", 100]
				},
			};
		});

		frm.set_query("item_code", "items", (doc, cdt, cdn) => {
			if (!doc.sales_order) {
				frappe.throw(__("Please select a Sales Order"));
			} else {
				let d = locals[cdt][cdn];
				return {
					query: "intan_pariwara.intan_pariwara.doctype.packing_list.packing_list.item_details",
					filters: {
						sales_order: doc.sales_order,
					},
				};
			}
		});
	},

	refresh: (frm) => {
		if (frm.doc.docstatus == 1) {
			if(frm.doc.per_delivered < 100){
				frm.add_custom_button(
					__("Delivery Note"),
					() => {
						frappe.model.open_mapped_doc({
							method: "intan_pariwara.intan_pariwara.doctype.packing_list.packing_list.make_delivery_note",
							frm: frm,
							freeze: true,
							freeze_message: __("Creating Delivery Note ..."),
						});
					},
					__("Create")
				);
			}
		}
	},

	sales_order: (frm) => {
		frm.set_value("items", null);

		if (frm.doc.sales_order) {
			erpnext.utils.map_current_doc({
				method: "intan_pariwara.intan_pariwara.custom.sales_order.make_packing",
				source_name: frm.doc.sales_order,
				target_doc: frm,
				freeze: true,
				freeze_message: __("Creating Packing List ..."),
			});
		}
	},
});
