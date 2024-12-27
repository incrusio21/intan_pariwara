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

	refresh(doc, dt, dn) {
		super.refresh(doc, dt, dn);
		
		var me = this;

		if (doc.docstatus == 1 && doc.per_ordered < 100) {
			me.frm.add_custom_button(__("Sales Order"), () => this.make_sales_order(), __("Create"));

			cur_frm.page.set_inner_btn_group_as_primary(__("Create"));
		}
	}

	fund_source(){
		var me = this;
		if(!me.frm.doc.fund_source){
			return 
		}

		if(!me.frm.doc.customer){
			frappe.msgprint(__("Please specify") + ": Customer. " + __("It is needed to fetch Fund Source."));
			this.frm.set_value("fund_source", "")
		}else{
			frappe.call({
				method: "intan_pariwara.controllers.queries.get_price_list_fund",
				args: {
					customer: me.frm.doc.customer,
					fund_source: me.frm.doc.fund_source,
				},
				callback: function (r) {
					if (r.message) {
						frappe.run_serially([
							() => me.frm.set_value(r.message),
							() => {
								me.apply_price_list();
							},
						]);
					}
				},
			});
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

	rebate(doc, cdt, cdn) {
		this.price_list_rate(doc, cdt, cdn)
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
	
	calculate_item_values() {
		var me = this;
		if (!this.discount_amount_applied) {
			for (const item of this.frm.doc.items || []) {
				frappe.model.round_floats_in(item);
				item.net_rate = item.rate;
				item.qty = item.qty === undefined ? (me.frm.doc.is_return ? -1 : 1) : item.qty;

				if (!(me.frm.doc.is_return || me.frm.doc.is_debit_note)) {
					item.net_amount = item.amount = flt(item.rate * item.qty, precision("amount", item));
					item.rebate_amount = flt((item.price_list_rate * item.rebate / 100) * item.qty, precision("rebate_amount", item))
				}
				else {
					// allow for '0' qty on Credit/Debit notes
					let qty = flt(item.qty);
					if (!qty) {
						qty = (me.frm.doc.is_debit_note ? 1 : -1);
						if (me.frm.doc.doctype !== "Purchase Receipt" && me.frm.doc.is_return === 1) {
							// In case of Purchase Receipt, qty can be 0 if all items are rejected
							qty = flt(item.qty);
						}
					}

					item.net_amount = item.amount = flt(item.rate * qty, precision("amount", item));
				}
				
				item.item_tax_amount = 0.0;
				item.total_weight = flt(item.weight_per_unit * item.stock_qty);

				me.set_in_company_currency(item, ["price_list_rate", "rate", "amount", "net_rate", "net_amount"]);
			}
		}
	}

	calculate_net_total() {
		var me = this;
		this.frm.doc.total_qty = this.frm.doc.total = this.frm.doc.base_total = this.frm.doc.net_total = this.frm.doc.base_net_total = 
			this.frm.doc.base_rebate_total = this.frm.doc.rebate_total = 0.0;

		$.each(this.frm._items || [], function(i, item) {
			me.frm.doc.total += item.amount;
			me.frm.doc.total_qty += item.qty;
			me.frm.doc.base_total += item.base_amount;
			me.frm.doc.net_total += item.net_amount;
			me.frm.doc.base_net_total += item.base_net_amount;
			me.frm.doc.base_rebate_total += item.rebate_amount;
			me.frm.doc.rebate_total += item.rebate_amount;
		});

		frappe.model.round_floats_in(this.frm.doc, ["total", "base_total", "net_total", "base_net_total", "base_rebate_total", "rebate_total"]);
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