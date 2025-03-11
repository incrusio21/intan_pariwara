// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Packing List", {
	setup: (frm) => {
		frm.set_query("warehouse", () => {
			return {
				filters: {
					is_group: 0,
				},
			};
		});

		frm.set_query("doc_name", (doc) => {
			var filters = {
				docstatus: 1,
				per_packing: ["<", 100]
			}

			if(doc.purpose == "Material Request"){
				filters["material_request_type"] = "Material Transfer"
			}

			return {
				filters: filters,
			};
		});

		frm.set_query("item_code", "items", (doc, cdt, cdn) => {
			if (!doc.doc_name) {
				frappe.throw(__("Please select a " + doc.purpose));
			} else {
				let d = locals[cdt][cdn];
				return {
					query: "intan_pariwara.intan_pariwara.doctype.packing_list.packing_list.item_details",
					filters: {
						sales_order: doc.doc_name,
					},
				};
			}
		});
	},

	refresh: (frm) => {
		if (frm.doc.docstatus == 1) {
			if(frm.doc.purpose == "Sales Order" && frm.doc.per_delivered < 100){
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

			if(frm.doc.purpose == "Material Request" && frm.doc.per_delivered < 100){
				frm.add_custom_button(
					__("Material Transfer"),
					() => {
						frappe.model.open_mapped_doc({
							method: "intan_pariwara.intan_pariwara.doctype.packing_list.packing_list.make_stock_entry",
							frm: frm,
							freeze: true,
							freeze_message: __("Creating Material Transfer ..."),
						});
					},
					__("Create")
				);
			}
		}
	},

	purpose: (frm) => {
		frm.events.doc_name(frm)
	},

	doc_name: (frm) => {
		frm.set_value("items", null);
		
		var purpose_method = {
			"Material Request": "intan_pariwara.intan_pariwara.custom.material_request.make_packing_list",
			"Sales Order": "intan_pariwara.intan_pariwara.custom.sales_order.make_packing_list",
		}

		if (frm.doc.doc_name) {
			frm.events.get_items(frm, purpose_method[frm.doc.purpose])
		}
	},

	get_items: (frm, method) => {
		erpnext.utils.map_current_doc({
			method: method,
			source_name: frm.doc.doc_name,
			target_doc: frm,
			freeze: true,
			freeze_message: __("Creating Packing List ..."),
		});
	},
});
