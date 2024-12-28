// Copyright (c) 2024, DAS and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("intan_pariwara.selling");

intan_pariwara.sales_common = {
    setup_selling_controller: function (extend_class) {
        // erpnext.sales_common.setup_selling_controller();

        intan_pariwara.selling.SellingController = class SellingController extends extend_class {
            
            fund_source(doc){
                var me = this;
                if(!doc.fund_source){
                    return 
                }

                if(!doc.customer){
                    frappe.msgprint(__("Please specify") + ": Customer. " + __("It is needed to fetch Fund Source."));
                    this.frm.set_value("fund_source", "")
                }else{
                    frappe.call({
                        method: "intan_pariwara.controllers.queries.get_price_list_fund",
                        args: {
                            company: doc.company,
                            customer: doc.customer,
                            fund_source: doc.fund_source,
                            rebate_from: doc.rebate_account_from,
                            rebate_to: doc.rebate_account_to,
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
            
            rebate(doc, cdt, cdn) {
                var item = frappe.get_doc(cdt, cdn);
                if(doc.transaction_type == "Reguler" && item.rebate > item.rebate_max){
                    frappe.msgprint(__("Maximum Rebate limit exceeded."))
                    item.rebate = item.rebate_max
                }
        
                this.price_list_rate(doc, cdt, cdn)
            }
        
            change_form_labels(company_currency) {
                let me = this;
        
                this.frm.set_currency_labels(["base_total", "base_net_total", "base_total_taxes_and_charges",
                    "base_discount_amount", "base_grand_total", "base_rounded_total", "base_in_words",
                    "base_taxes_and_charges_added", "base_taxes_and_charges_deducted", "total_amount_to_pay",
                    "base_paid_amount", "base_write_off_amount", "base_change_amount", "base_operating_cost",
                    "base_raw_material_cost", "base_total_cost", "base_scrap_material_cost",
                    "base_rounding_adjustment"], company_currency);
        
                this.frm.set_currency_labels(["total", "net_total", "total_taxes_and_charges", "discount_amount",
                    "grand_total", "taxes_and_charges_added", "taxes_and_charges_deducted","tax_withholding_net_total",
                    "rounded_total", "in_words", "paid_amount", "write_off_amount", "operating_cost",
                    "scrap_material_cost", "rounding_adjustment", "raw_material_cost",
                    "total_cost"], this.frm.doc.currency);
        
                this.frm.set_currency_labels(["outstanding_amount", "total_advance"],
                    this.frm.doc.party_account_currency);
        
                this.frm.set_df_property("conversion_rate", "description", "1 " + this.frm.doc.currency
                    + " = [?] " + company_currency);
        
                if(this.frm.doc.price_list_currency && this.frm.doc.price_list_currency!=company_currency) {
                    this.frm.set_df_property("plc_conversion_rate", "description", "1 "
                        + this.frm.doc.price_list_currency + " = [?] " + company_currency);
                }
        
                // toggle fields
                this.frm.toggle_display(["conversion_rate", "base_total", "base_net_total", "base_tax_withholding_net_total",
                    "base_total_taxes_and_charges", "base_taxes_and_charges_added", "base_taxes_and_charges_deducted",
                    "base_grand_total", "base_rounded_total", "base_in_words", "base_discount_amount",
                    "base_paid_amount", "base_write_off_amount", "base_operating_cost", "base_raw_material_cost",
                    "base_total_cost", "base_scrap_material_cost", "base_rounding_adjustment", "base_rebate_total"],
                this.frm.doc.currency != company_currency);
        
                this.frm.toggle_display(["plc_conversion_rate", "price_list_currency"],
                    this.frm.doc.price_list_currency != company_currency);
        
                let show = cint(this.frm.doc.discount_amount) ||
                        ((this.frm.doc.taxes || []).filter(function(d) {return d.included_in_print_rate===1}).length);
        
                if(this.frm.doc.doctype && frappe.meta.get_docfield(this.frm.doc.doctype, "net_total")) {
                    this.frm.toggle_display("net_total", show);
                }
        
                if(this.frm.doc.doctype && frappe.meta.get_docfield(this.frm.doc.doctype, "base_net_total")) {
                    this.frm.toggle_display("base_net_total", (show && (me.frm.doc.currency != company_currency)));
                }
            }
        
            update_item_grid_labels(company_currency) {
                this.frm.set_currency_labels([
                    "base_rate", "base_net_rate", "base_price_list_rate",
                    "base_amount", "base_net_amount", "base_rate_with_margin", "base_rebate_amount"
                ], company_currency, "items");
        
                this.frm.set_currency_labels([
                    "rate", "net_rate", "price_list_rate", "amount",
                    "net_amount", "stock_uom_rate", "rate_with_margin", "rebate_amount"
                ], this.frm.doc.currency, "items");
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
        
                        me.set_in_company_currency(item, ["price_list_rate", "rate", "amount", "net_rate", "net_amount", "rebate_amount"]);
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
    }
}