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

	discount_percent(frm){
		frm.doc.items.forEach((item) => {
			frappe.model.set_value(item.doctype, item.name, "discount_percentage", frm.doc.discount_percent || 0)			
		});
	}
});

intan_pariwara.selling.PreOrderController = class PreOrderController extends intan_pariwara.selling.SellingController {
    onload(doc, dt, dn) {
		super.onload(doc, dt, dn);
	}

	refresh(doc, dt, dn) {
		super.refresh(doc, dt, dn);
		
		var me = this;
		
		if (doc.docstatus == 1 && doc.per_ordered < 100) {
			me.frm.add_custom_button(__("Sales Order"), () => this.make_sales_order(), __("Create"));

			cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
		}

		if(!(doc.__islocal || doc.otp_verified)){
			me.frm.add_custom_button(
				__("OTP Verified"), () => {
					frappe.prompt(
						{
							fieldtype: "Data",
							label: __("One Time Password"),
							fieldname: "otp",
							reqd: 1,
						},
						(data) => {
							frappe.call({
								method: "otp_verification",
								doc: doc,
								args: {
									otp: data.otp
								}
							}).then((data) => {
								me.frm.refresh()
							})
						},
						__("Input One Time Password"),
						__("Submit")
					);
				}
			)
		}
	}

    party_name() {
		var me = this;
		erpnext.utils.get_party_details(this.frm, null, null, function () {
			me.apply_price_list();
		});

		if (me.frm.doc.quotation_to == "Lead" && me.frm.doc.party_name) {
			me.frm.trigger("get_lead_details");
		}
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