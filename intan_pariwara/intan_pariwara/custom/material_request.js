// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Material Request", "make_custom_buttons")
frappe.ui.form.on("Material Request", {
    refresh: function (frm) {
		frm.set_query("purpose", () => {
			return {
				filters: {
					on_material_request: 1,
				},
			};
		});

        // if (frm.doc.docstatus == 1 && frm.doc.status != "Stopped" 
        //     && frm.doc.material_request_type === "Material Transfer"
        //     && flt(frm.doc.per_packing, precision) < 100) {
        //         frm.add_custom_button(
        //             __("Packing List"),
        //             () => {
        //                 frappe.model.open_mapped_doc({
        //                     method: "intan_pariwara.intan_pariwara.custom.material_request.make_packing_list",
        //                     frm: frm,
        //                 });
        //             },
        //             __("Create")
        //         );
        // }
    },
	
    make_custom_buttons: function (frm) {
		if (frm.doc.docstatus == 0) {
			frm.add_custom_button(
				__("Bill of Materials"),
				() => frm.events.get_items_from_bom(frm),
				__("Get Items From")
			);
		}

		if (frm.doc.docstatus == 1 && frm.doc.status != "Stopped") {
			let precision = frappe.defaults.get_default("float_precision");

			if (flt(frm.doc.per_received, precision) < 100) {
				frm.add_custom_button(__("Stop"), () => frm.events.update_status(frm, "Stopped"));
			}

			if (flt(frm.doc.per_ordered, precision) < 100) {
				let add_create_pick_list_button = () => {
					frm.add_custom_button(
						__("Pick List"),
						() => frm.events.create_pick_list(frm),
						__("Create")
					);
				};
				
				frappe.db.get_value("Purpose Request", frm.doc.purpose, "on_pick_list", (data) => {
					if (data.on_pick_list) {
						add_create_pick_list_button();
						// frm.add_custom_button(
						// 	__("Material Transfer"),
						// 	() => frm.events.make_stock_entry(frm),
						// 	__("Create")
						// );
	
						// frm.add_custom_button(
						// 	__("Material Transfer (In Transit)"),
						// 	() => frm.events.make_in_transit_stock_entry(frm),
						// 	__("Create")
						// );
					}
				})

				if (frm.doc.purpose === "Material Issue") {
					frm.add_custom_button(
						__("Issue Material"),
						() => frm.events.make_stock_entry(frm),
						__("Create")
					);
				}

				if (frm.doc.material_request_type === "Customer Provided") {
					frm.add_custom_button(
						__("Material Receipt"),
						() => frm.events.make_stock_entry(frm),
						__("Create")
					);
				}

				if (frm.doc.material_request_type === "Purchase") {
					frm.add_custom_button(
						__("Purchase Order"),
						() => frm.events.make_purchase_order(frm),
						__("Create")
					);
				}

				if (frm.doc.material_request_type === "Purchase") {
					frm.add_custom_button(
						__("Request for Quotation"),
						() => frm.events.make_request_for_quotation(frm),
						__("Create")
					);
				}

				if (frm.doc.material_request_type === "Purchase") {
					frm.add_custom_button(
						__("Supplier Quotation"),
						() => frm.events.make_supplier_quotation(frm),
						__("Create")
					);
				}

				if (frm.doc.material_request_type === "Manufacture") {
					frm.add_custom_button(
						__("Work Order"),
						() => frm.events.raise_work_orders(frm),
						__("Create")
					);
				}

				frm.page.set_inner_btn_group_as_primary(__("Create"));
			}
		}

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Sales Order"),
				() => frm.events.get_items_from_sales_order(frm),
				__("Get Items From")
			);
		}

		if (frm.doc.docstatus == 1 && frm.doc.status == "Stopped") {
			frm.add_custom_button(__("Re-open"), () => frm.events.update_status(frm, "Submitted"));
		}
	},

	purpose: function (frm) {
		if(!frm.doc.purpose) return

		frappe.db.get_value("Purpose Request", frm.doc.purpose, "purpose", (data) => {
			frm.set_value("material_request_type", data.purpose)
		})
	}
})