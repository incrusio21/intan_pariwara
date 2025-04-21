// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt
frappe.provide("intan_pariwara.selling")

cur_frm.cscript.tax_table = "Sales Taxes and Charges";

erpnext.accounts.taxes.setup_tax_validations("Sales Taxes and Charges Template");
erpnext.accounts.taxes.setup_tax_filters("Sales Taxes and Charges");
erpnext.sales_common.setup_selling_controller();
intan_pariwara.sales_common.setup_selling_controller(erpnext.selling.SellingController)

frappe.ui.form.on("Pre Order", {
	setup: function (frm) {

		frm.set_df_property("packed_items", "cannot_add_rows", true);
		frm.set_df_property("packed_items", "cannot_delete_rows", true);

		frm.set_query("serial_and_batch_bundle", "packed_items", (doc, cdt, cdn) => {
			let row = locals[cdt][cdn];
			return {
				filters: {
					item_code: row.item_code,
					voucher_type: doc.doctype,
					voucher_no: ["in", [doc.name, ""]],
					is_cancelled: 0,
				},
			};
		});



	},
	refresh(frm) {
		frm.trigger("set_label");
		frm.trigger("set_dynamic_field_label");

		let sbb_field = frm.get_docfield("packed_items", "serial_and_batch_bundle");
		if (sbb_field) {
			sbb_field.get_route_options_for_new_doc = (row) => {
				return {
					item_code: row.doc.item_code,
					warehouse: row.doc.warehouse,
					voucher_type: frm.doc.doctype,
				};
			};
		}
	},

	set_label: function (frm) {
		frm.fields_dict.customer_address.set_label(__(frm.doc.quotation_to + " Address"));
	},

	discount_percent(frm) {
		frm.doc.items.forEach((item) => {
			frappe.model.set_value(item.doctype, item.name, "discount_percentage", frm.doc.discount_percent || 0)
		});
	},
	discount_percent_rebate(frm) {
		frm.doc.items.forEach((item) => {
			frappe.model.set_value(item.doctype, item.name, "rebate", frm.doc.discount_percent_rebate || 0)
		});
	}
});

frappe.ui.form.on('Pre Order Item', {
	items_add(frm, cdt, cdn) {
		frm.doc.items.forEach((item) => {
			frappe.model.set_value(item.doctype, item.name, "rebate", 0)
		});
	}
});

intan_pariwara.selling.PreOrderController = class PreOrderController extends intan_pariwara.selling.SellingController {
	refresh(doc, dt, dn) {
		super.refresh(doc, dt, dn);

		var me = this;

		if (doc.docstatus == 1) {
			if(doc.per_ordered < 100){

				me.frm.add_custom_button(__("Sales Order"), () => this.make_sales_order(), __("Create"));
			}
			
			if(doc.custom_calon_siplah == 'Ya' &&
				doc.delivery_before_po_siplah == "Ya" && 
				doc.per_ordered == 0 && 
				doc.per_request < 100){
				me.frm.add_custom_button(__("Material Request"), () => this.make_material_request(), __("Create"));
			}

			if(cur_frm.page.get_inner_group_button("Create")){
				cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
			}
		}

		new intan_pariwara.utils.OtpVerified({ frm: this.frm });
	}

	make_material_request() {
		var me = this;
		
		frappe.model.open_mapped_doc({
			method: "intan_pariwara.intan_pariwara.doctype.pre_order.pre_order.make_material_request",
			frm: me.frm,
		});
	}

	make_sales_order() {
		var me = this;

		let has_alternative_item = this.frm.doc.items.some((item) => item.is_alternative);
		if (has_alternative_item) {
			this.show_alternative_items_dialog();
		} else {
			frappe.model.open_mapped_doc({
				method: "intan_pariwara.intan_pariwara.doctype.pre_order.pre_order.make_sales_order",
				frm: me.frm,
			});
		}
	}
}

cur_frm.script_manager.make(intan_pariwara.selling.PreOrderController);