// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Packing List", {
	setup: (frm) => {
		frm.set_df_property("items", "cannot_add_rows", true);
		frm.set_df_property("items_retail", "cannot_add_rows", true);

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
		
		// var purpose_method = {
		// 	"Material Request": "intan_pariwara.intan_pariwara.custom.material_request.make_packing_list",
		// 	"Sales Order": "intan_pariwara.intan_pariwara.custom.sales_order.make_packing_list",
		// }

		// if (frm.doc.doc_name) {
		// 	frm.events.get_items(frm, purpose_method[frm.doc.purpose])
		// }
	},

	get_items: (frm, method) => {
		const fields = [
			{
				fieldtype: "Data",
				fieldname: "document_detail",
				read_only: 1,
				hidden: 1,
			},
			{
				fieldtype: "Link",
				fieldname: "item_code",
				options: "Item",
				in_list_view: 1,
				read_only: 1,
				disabled: 0,
				label: __("Item Code")
			},
			{
				fieldtype: "Link",
				fieldname: "stock_uom",
				options: "UOM",
				in_list_view: 1,
				read_only: 1,
				disabled: 0,
				label: __("UOM")
			},
			{
				fieldtype: "Float",
				fieldname: "remaining_qty",
				default: 0,
				read_only: 1,
				in_list_view: 1,
				label: __("Remaining Qty"),
			},
			{
				fieldtype: "Float",
				fieldname: "qty",
				default: 0,
				read_only: 0,
				in_list_view: 1,
				label: __("Qty"),
			},
			{
				fieldtype: "Float",
				fieldname: "qty_per_koli",
				default: 0,
				read_only: 0,
				in_list_view: 1,
				label: __("Qty/Koli"),
			},
		]

		frappe.call({
			method: "intan_pariwara.intan_pariwara.doctype.packing_list.packing_list.get_items",
			args: {
				doctype: frm.doc.purpose,
				docname: frm.doc.doc_name,
				used_item: [...(frm.doc.items || []), ...(frm.doc.items_retail || [])]
			},
			freeze: true,
			callback: function(data){
				if(data.message.length == 0){
					frappe.throw(__("All items have been included in the packaging."))
				}

				let dialog = new frappe.ui.Dialog({
					title: __("Get Packing Items"),
					size: "extra-large",
					fields: [
						{
							fieldname: "is_retail",
							fieldtype: "Check",
							label: "Is Retail",
						},
						{
							fieldname: "trans_items",
							fieldtype: "Table",
							label: "Items",
							cannot_add_rows: 1,
							cannot_delete_rows: 1,
							in_place_edit: false,
							reqd: 1,
							data: data.message,
							get_data: () => {
								return data.message;
							},
							fields: fields,
						}
					],
					primary_action: function () {
						const trans_items = this.get_values()["trans_items"].filter((item) => !!item.qty);
						
						if(trans_items.length == 0){
							frappe.throw("Please fill in the quantity on one of the rows")
						}

						frappe.call({
							method: "intan_pariwara.intan_pariwara.doctype.packing_list.packing_list.update_items",
							freeze: true,
							args: {
								is_retail: this.get_values()["is_retail"],
								trans_items: trans_items,
							},
							callback: function (data) {
								if(data.message){
									data.message.package.forEach(value => {
										var p = frm.add_child("items");
										frappe.model.set_value(p.doctype, p.name, value)
									});

									data.message.retail.forEach(value => {
										var r = frm.add_child("items_retail");
										r.retail_key = data.message.retail_key
										frappe.model.set_value(r.doctype, r.name, value)
									});

									dialog.hide();
									refresh_field("items");
									refresh_field("items_retail");
								}
							},
						});
					},
					primary_action_label: __("Set Koli"),
				})

				dialog.show();
			}
		})
		// erpnext.utils.map_current_doc({
		// 	method: method,
		// 	source_name: frm.doc.doc_name,
		// 	target_doc: frm,
		// 	freeze: true,
		// 	freeze_message: __("Creating Packing List ..."),
		// });
	},
});
