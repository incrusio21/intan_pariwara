// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt

frappe.ui.form.off("Sales Order", "refresh")
frappe.ui.form.on("Sales Order", {
    refresh: function (frm) {
		if (frm.doc.docstatus === 1) {
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
	}
})