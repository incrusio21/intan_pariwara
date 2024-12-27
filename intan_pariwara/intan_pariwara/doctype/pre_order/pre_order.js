// Copyright (c) 2024, DAS and contributors
// For license information, please see license.txt

cur_frm.cscript.tax_table = "Sales Taxes and Charges";

erpnext.accounts.taxes.setup_tax_validations("Sales Taxes and Charges Template");
erpnext.accounts.taxes.setup_tax_filters("Sales Taxes and Charges");
erpnext.sales_common.setup_selling_controller();

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
});

erpnext.selling.PreOrderController = class PreOrderController extends erpnext.selling.SellingController {
    onload(doc, dt, dn) {
		super.onload(doc, dt, dn);
	}

	fund_source(){
		var me = this;

		frappe.call({
			method: "intan_pariwara.controllers.queries.get_price_list_fund",
			args: {
				customer: frm.doc.customer,
				fund_source: frm.doc.fund_source,
			},
			callback: function (r) {
				if (r.message) {
					frappe.run_serially([
						() => frm.set_value(r.message),
						() => {
							me.apply_price_list();
						},
					]);
				}
			},
		});
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

    calculate_totals() {
		// Changing sequence can cause rounding_adjustmentng issue and on-screen discrepency
		var me = this;
		var tax_count = this.frm.doc["taxes"] ? this.frm.doc["taxes"].length : 0;
		this.frm.doc.grand_total = flt(tax_count
			? this.frm.doc["taxes"][tax_count - 1].total + flt(this.frm.doc.grand_total_diff)
			: this.frm.doc.net_total);

        this.frm.doc.base_grand_total = (this.frm.doc.total_taxes_and_charges) ?
            flt(this.frm.doc.grand_total * this.frm.doc.conversion_rate) : this.frm.doc.base_net_total;
		
		this.frm.doc.total_taxes_and_charges = flt(this.frm.doc.grand_total - this.frm.doc.net_total
			- flt(this.frm.doc.rounding_adjustment), precision("total_taxes_and_charges"));

		this.set_in_company_currency(this.frm.doc, ["total_taxes_and_charges", "rounding_adjustment"]);

		// Round grand total as per precision
		frappe.model.round_floats_in(this.frm.doc, ["grand_total", "base_grand_total"]);

		// rounded totals
		this.set_rounded_total();
	}
}

cur_frm.script_manager.make(erpnext.selling.PreOrderController);