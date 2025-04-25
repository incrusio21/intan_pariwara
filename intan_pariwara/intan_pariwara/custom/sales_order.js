// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
intan_pariwara.sales_common.setup_selling_controller(erpnext.selling.SalesOrderController)

frappe.ui.form.off("Sales Order", "refresh")
frappe.ui.form.on("Sales Order", {
    refresh: function (frm) {
		if (frm.doc.docstatus === 1 && frm.doc.workflow_state === "Approved") {
			if (
				frm.doc.status !== "Closed" &&
				flt(frm.doc.per_delivered) < 100 &&
				flt(frm.doc.per_billed) < 100 &&
				frm.has_perm("write")
			) {
				if(frappe.boot.user.update_item){
					frm.add_custom_button(__("Update Items"), () => {
						erpnext.utils.update_child_items({
							frm: frm,
							child_docname: "items",
							child_doctype: "Sales Order Detail",
							cannot_add_row: false,
							has_reserved_stock: frm.doc.__onload && frm.doc.__onload.has_reserved_stock,
						});
					});
				}

				// Stock Reservation > Reserve button should only be visible if the SO has unreserved stock and no Pick List is created against the SO.
				if (
					frm.doc.__onload &&
					frm.doc.__onload.has_unreserved_stock &&
					flt(frm.doc.per_picked) === 0
				) {
					frm.add_custom_button(
						__("Reserve"),
						() => frm.events.create_stock_reservation_entries(frm),
						__("Stock Reservation")
					);
				}
			}

			// Stock Reservation > Unreserve button will be only visible if the SO has un-delivered reserved stock.
			if (
				frm.doc.__onload &&
				frm.doc.__onload.has_reserved_stock &&
				frappe.model.can_cancel("Stock Reservation Entry")
			) {
				frm.add_custom_button(
					__("Unreserve"),
					() => frm.events.cancel_stock_reservation_entries(frm),
					__("Stock Reservation")
				);
			}

			frm.doc.items.forEach((item) => {
				if (flt(item.stock_reserved_qty) > 0 && frappe.model.can_read("Stock Reservation Entry")) {
					frm.add_custom_button(
						__("Reserved Stock"),
						() => frm.events.show_reserved_stock(frm),
						__("Stock Reservation")
					);
					return;
				}
			});
		}

		if (frm.doc.docstatus === 0) {
			if (frm.doc.is_internal_customer) {
				frm.events.get_items_from_internal_purchase_order(frm);
			}

			if (frm.doc.docstatus === 0) {
				frappe.call({
					method: "erpnext.selling.doctype.sales_order.sales_order.get_stock_reservation_status",
					callback: function (r) {
						if (!r.message) {
							frm.set_value("reserve_stock", 0);
							frm.set_df_property("reserve_stock", "read_only", 1);
							frm.set_df_property("reserve_stock", "hidden", 1);
							frm.fields_dict.items.grid.update_docfield_property("reserve_stock", "hidden", 1);
							frm.fields_dict.items.grid.update_docfield_property(
								"reserve_stock",
								"default",
								0
							);
							frm.fields_dict.items.grid.update_docfield_property(
								"reserve_stock",
								"read_only",
								1
							);
						}
					},
				});
			}
		}

		// Hide `Reserve Stock` field description in submitted or cancelled Sales Order.
		if (frm.doc.docstatus > 0) {
			frm.set_df_property("reserve_stock", "description", null);
		}

		if (!frm.is_new() && frm.doc.custom_no_siplah){
			frm.set_df_property("custom_no_siplah", "options", [frm.doc.custom_no_siplah]);
			if (frm.doc.custom_no_siplah) frm.events.custom_no_siplah(frm);
			if (frm.doc.docstatus == 1) frm.set_df_property("custom_no_siplah", "read_only", 1);
			
		} else {
			frm.events.show_load_siplah(frm);
		}
	},
	show_load_siplah(frm){
		frm.add_custom_button("Load SIPLAH",function(){
				if (frm.doc.custom_calon_siplah == "Ya" && (frm.doc.relasi || frm.doc.customer)){
					frappe.call({
						"method":"intan_pariwara.siplah_integration.sales_order.get_list_siplah",
						"args": {
							"customer": frm.doc.customer,
							"relasi": frm.doc.relasi

						},
						callback:function(r){
							if (r.message){
								var list_siplah = [];
								var full_siplah = [];
								for (var i = r.message.length - 1; i >= 0; i--) {
									list_siplah.push(r.message[i]["nomor_order"]);
									full_siplah.push({"nomor_order": r.message[i]["nomor_order"],"janji_bayar":r.message[i]["janji_bayar"]});
								}
								frm.set_df_property("custom_no_siplah", "options",list_siplah);
								frm.set_value("siplah_json",full_siplah);
								frm.refresh_fields();
							}
						}
					})
				}else{
					// kosongkan select jika calon siplah tidak sama ya dan relasi atau customer kosong
					frm.set_df_property("custom_no_siplah", "options", []);
				}
				
				frm.set_value("custom_no_siplah", "");
			},"SIPLAH")
	},
	
	customer(frm){
		// cukup trigger event custom_calon_siplah
		frm.events.custom_calon_siplah(frm)
	},
	custom_calon_siplah(frm){
		frm.set_df_property("custom_no_siplah", "options", []);	
	},
	custom_no_siplah(frm){
		if(!frm.doc.custom_no_siplah) {
			if (frm.doc.custom_calon_siplah == "Ya"){
				frm.events.show_load_siplah(frm);
			}
		}
		
		if (frm.doc.custom_calon_siplah == "Ya" && (frm.doc.relasi || frm.doc.customer)) {		

			frm.add_custom_button("Update SIPLAH Items",function(){
				console.log(frm.doc.siplah_json)
				// check jika dari preorder
				frappe.call({
					method: "get_items",
					freeze: true,
					doc: frm.doc,
					callback:function(data){
						frm.refresh_fields();
					}
				})
			},"SIPLAH")
			
			frappe.call({
				method: "update_siplah_table",
				freeze: true,
				doc: frm.doc,
				callback:function(data){
					frm.refresh_field("tabel_siplah_items");
				}
			})
		}
	},
	check_bin_siplah(frm){
		frappe.call({
			method: "validate_bin_siplah",
			freeze: true,
			doc: frm.doc,
			args: {
				update: true
			},
			callback:function(data){
				frm.refresh_fields();
			}
		})
	},
	before_save(frm){
		frm.set_value("siplah_json","");
		if (frm.doc.payment_schedule.length > 0 && frm.doc.grand_total > 0){
			frm.doc.payment_schedule[0].payment_amount = frm.doc.grand_total;
		}

		if (frm.doc.delivery_date){
			frm.trigger("delivery_date");
		}
	}
})

intan_pariwara.selling.SalesOrderController = class SalesOrderController extends intan_pariwara.selling.SellingController {
	refresh(doc, dt, dn) {
		var me = this;
		super.refresh(doc, dt, dn);

		// if (doc.docstatus == 1 && doc.workflow_state === "Approved") {
		// 	if (
		// 		doc.status !== "Closed" &&
		// 		flt(doc.per_picked) < 100
		// 	) {
		// 		if (frappe.model.can_create("Packing List")) {
		// 			this.frm.add_custom_button(
		// 				__("Packing List"),
		// 				() => {
		// 					frappe.model.open_mapped_doc({
		// 						method: "intan_pariwara.intan_pariwara.custom.sales_order.make_packing_list",
		// 						frm: me.frm,
		// 						freeze: true,
		// 						freeze_message: __("Creating Packing List ..."),
		// 					});
		// 				},
		// 				__("Create")
		// 			);
		// 		}
		// 	}
		// }
		
		if(doc.delivery_before_po_siplah == "Ya"){
			me.frm.remove_custom_button(__("Pick List"), __("Create"));
		}else{
			me.frm.remove_custom_button(__("Delivery Note"), __("Create"));
		}

		if(doc.docstatus == 1 && doc.workflow_state !== "Approved"){
			me.frm.clear_custom_buttons()
		}
	}

	make_delivery_note(delivery_dates, for_reserved_stock = false) {
		let method = this.frm.doc.delivery_before_po_siplah == "Ya" ? 
			"intan_pariwara.intan_pariwara.custom.sales_order.make_delivery_note_advance"
			: "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note"
		frappe.model.open_mapped_doc({
			method: method,
			frm: this.frm,
			args: {
				delivery_dates,
				for_reserved_stock: for_reserved_stock,
			},
			freeze: true,
			freeze_message: __("Creating Delivery Note ..."),
		});
	}
}

cur_frm.script_manager.make(intan_pariwara.selling.SalesOrderController);