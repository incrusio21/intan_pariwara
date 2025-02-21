// Copyright (c) 2024, DAS and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("intan_pariwara.selling");

intan_pariwara.sales_common = {
    setup_selling_controller: function (extend_class) {
        // erpnext.sales_common.setup_selling_controller();

        intan_pariwara.selling.SellingController = class SellingController extends extend_class {
            refresh(doc, dt, dn) {
                super.refresh(doc, dt, dn);
                
                var me = this;

                me.frm.set_query("relasi", function(doc){
                    if(!doc.relasi_group){
                        frappe.throw("Please Set Customer Group in Doctype Jenis Relasi First")
                    }

                    return {
                        filters: {
                            customer_group: doc.relasi_group
                        },
                    }
                })
            }
            item_code(doc, cdt, cdn) {
                var me = this;
                var item = frappe.get_doc(cdt, cdn);
                var update_stock = 0, show_batch_dialog = 0;
        
                item.weight_per_unit = 0;
                item.weight_uom = '';
                item.conversion_factor = 0;
        
                if(['Sales Invoice', 'Purchase Invoice'].includes(this.frm.doc.doctype)) {
                    update_stock = cint(me.frm.doc.update_stock);
                    show_batch_dialog = update_stock;
        
                } else if((this.frm.doc.doctype === 'Purchase Receipt') ||
                    this.frm.doc.doctype === 'Delivery Note') {
                    show_batch_dialog = 1;
                }
        
                if (show_batch_dialog && item.use_serial_batch_fields === 1) {
                    show_batch_dialog = 0;
                }
        
                item.barcode = null;
        
                if(item.item_code || item.serial_no) {
                    if(!this.validate_company_and_party()) {
                        this.frm.fields_dict["items"].grid.grid_rows[item.idx - 1].remove();
                    } else {
                        item.pricing_rules = ''
                        return this.frm.call({
                            method: "erpnext.stock.get_item_details.get_item_details",
                            child: item,
                            args: {
                                doc: me.frm.doc,
                                args: {
                                    item_code: item.item_code,
                                    barcode: item.barcode,
                                    serial_no: item.serial_no,
                                    batch_no: item.batch_no,
                                    set_warehouse: me.frm.doc.set_warehouse,
                                    warehouse: item.warehouse,
                                    customer: me.frm.doc.customer || me.frm.doc.party_name,
                                    quotation_to: me.frm.doc.quotation_to,
                                    supplier: me.frm.doc.supplier,
                                    currency: me.frm.doc.currency,
                                    is_internal_supplier: me.frm.doc.is_internal_supplier,
                                    is_internal_customer: me.frm.doc.is_internal_customer,
                                    update_stock: update_stock,
                                    conversion_rate: me.frm.doc.conversion_rate,
                                    price_list: me.frm.doc.selling_price_list || me.frm.doc.buying_price_list,
                                    price_list_currency: me.frm.doc.price_list_currency,
                                    plc_conversion_rate: me.frm.doc.plc_conversion_rate,
                                    company: me.frm.doc.company,
                                    order_type: me.frm.doc.order_type,
                                    is_pos: cint(me.frm.doc.is_pos),
                                    is_return: cint(me.frm.doc.is_return),
                                    is_subcontracted: me.frm.doc.is_subcontracted,
                                    ignore_pricing_rule: me.frm.doc.ignore_pricing_rule,
                                    doctype: me.frm.doc.doctype,
                                    name: me.frm.doc.name,
                                    project: item.project || me.frm.doc.project,
                                    qty: item.qty || 1,
                                    net_rate: item.rate,
                                    base_net_rate: item.base_net_rate,
                                    stock_qty: item.stock_qty,
                                    conversion_factor: item.conversion_factor,
                                    weight_per_unit: item.weight_per_unit,
                                    uom: item.uom,
                                    weight_uom: item.weight_uom,
                                    manufacturer: item.manufacturer,
                                    stock_uom: item.stock_uom,
                                    pos_profile: cint(me.frm.doc.is_pos) ? me.frm.doc.pos_profile : '',
                                    cost_center: item.cost_center,
                                    tax_category: me.frm.doc.tax_category,
                                    item_tax_template: item.item_tax_template,
                                    child_doctype: item.doctype,
                                    child_docname: item.name,
                                    is_old_subcontracting_flow: me.frm.doc.is_old_subcontracting_flow,
                                }
                            },
        
                            callback: function(r) {
                                if(!r.exc) {
                                    frappe.run_serially([
                                        () => {
                                            if (item.docstatus === 0
                                                && frappe.meta.has_field(item.doctype, "use_serial_batch_fields")
                                                && !item.use_serial_batch_fields
                                                && cint(frappe.user_defaults?.use_serial_batch_fields) === 1
                                            ) {
                                                item["use_serial_batch_fields"] = 1;
                                            }
                                        },
                                        () => {
                                            var d = locals[cdt][cdn];
                                            me.add_taxes_from_item_tax_template(d.item_tax_rate);
                                            if (d.free_item_data && d.free_item_data.length > 0) {
                                                me.apply_product_discount(d);
                                            }
                                        },
                                        () => {
                                            // for internal customer instead of pricing rule directly apply valuation rate on item
                                            if ((me.frm.doc.is_internal_customer || me.frm.doc.is_internal_supplier) && me.frm.doc.represents_company === me.frm.doc.company) {
                                                me.get_incoming_rate(item, me.frm.posting_date, me.frm.posting_time,
                                                    me.frm.doc.doctype, me.frm.doc.company);
                                            } else {
                                                me.frm.script_manager.trigger("price_list_rate", cdt, cdn);
                                            }
                                        },
                                        () => {
                                            if (me.frm.doc.is_internal_customer || me.frm.doc.is_internal_supplier) {
                                                me.calculate_taxes_and_totals();
                                            }
                                        },
                                        () => me.toggle_conversion_factor(item),
                                        () => {
                                            if (show_batch_dialog && !frappe.flags.trigger_from_barcode_scanner)
                                                return frappe.db.get_value("Item", item.item_code, ["has_batch_no", "has_serial_no"])
                                                    .then((r) => {
                                                        if (r.message &&
                                                        (r.message.has_batch_no || r.message.has_serial_no)) {
                                                            frappe.flags.hide_serial_batch_dialog = false;
                                                        } else {
                                                            show_batch_dialog = false;
                                                        }
                                                    });
                                        },
                                        () => {
                                            // check if batch serial selector is disabled or not
                                            if (show_batch_dialog && !frappe.flags.hide_serial_batch_dialog)
                                                return frappe.db.get_single_value('Stock Settings', 'disable_serial_no_and_batch_selector')
                                                    .then((value) => {
                                                        if (value) {
                                                            frappe.flags.hide_serial_batch_dialog = true;
                                                        }
                                                    });
                                        },
                                        () => {
                                            if(show_batch_dialog && !frappe.flags.hide_serial_batch_dialog && !frappe.flags.dialog_set) {
                                                var d = locals[cdt][cdn];
                                                $.each(r.message, function(k, v) {
                                                    if(!d[k]) d[k] = v;
                                                });
        
                                                if (d.has_batch_no && d.has_serial_no) {
                                                    d.batch_no = undefined;
                                                }
        
                                                frappe.flags.dialog_set = true;
                                                erpnext.show_serial_batch_selector(me.frm, d, (item) => {
                                                    me.frm.script_manager.trigger('qty', item.doctype, item.name);
                                                    if (!me.frm.doc.set_warehouse)
                                                        me.frm.script_manager.trigger('warehouse', item.doctype, item.name);
                                                    me.apply_price_list(item, true);
                                                }, undefined, !frappe.flags.hide_serial_batch_dialog);
                                            } else {
                                                frappe.flags.dialog_set = false;
                                            }
                                        },
                                        () => me.conversion_factor(doc, cdt, cdn, true),
                                        () => me.remove_pricing_rule(item),
                                        () => {
                                            if (item.apply_rule_on_other_items) {
                                                let key = item.name;
                                                me.apply_rule_on_other_items({key: item});
                                            }
                                        },
                                        () => {
                                            var company_currency = me.get_company_currency();
                                            me.update_item_grid_labels(company_currency);
                                        },
                                        () => {
                                            if (me.frm.doc.is_rebate_fixed){
                                                var field = me.frm.doc.apply_rebate ? "rebate" : "discount_percentage"
                                                var additional = me.frm.doc.additional_rebate_disc || 0
                                                frappe.model.set_value(item.doctype, item.name, field, flt(item.rebate_fix + additional));
                                            }
                                        }
                                    ]);
                                }
                            }
                        });
                    }
                }
            }

            company(doc){
                frappe.run_serially([
                    () => super.company(doc),
                    () => this.get_rebate_account(doc)
                ])
            }

            fund_source(doc){
                this.get_rebate_account(doc)
            }
            
            transaction_type(doc){
                this.get_rebate_account(doc)
            }

            rebate(doc, cdt, cdn) {
                var item = frappe.get_doc(cdt, cdn);
                if(doc.apply_rebate && doc.is_max_rebate_applied && 
                    item.rebate_max && item.rebate > item.rebate_max){
                    frappe.msgprint(__("Maximum Rebate limit exceeded."))
                    item.rebate = item.rebate_max
                }
        
                this.price_list_rate(doc, cdt, cdn)
            }
            
            discount_percentage(doc, cdt, cdn) {
				var item = frappe.get_doc(cdt, cdn);
                if(!doc.apply_rebate && doc.is_max_rebate_applied && 
                    item.rebate_max && item.discount_percentage > item.rebate_max){
                    frappe.msgprint(__("Maximum Discount limit exceeded."))
                    item.discount_percentage = item.rebate_max
                }
				item.discount_amount = 0.0;
				this.apply_discount_on_item(doc, cdt, cdn, "discount_percentage");
			}
            
            _set_values_for_item_list(children) {
                const items_rule_dict = {};
        
                for (const child of children) {
                    const existing_pricing_rule = frappe.model.get_value(child.doctype, child.name, "pricing_rules");
        
                    for (const [key, value] of Object.entries(child)) {
                        if (!["doctype", "name"].includes(key)) {
                            if (key === "price_list_rate" && child.price_list_rate != value) {
                                frappe.model.set_value(child.doctype, child.name, "rate", value);
                            }
        
                            if (key === "pricing_rules") {
                                frappe.model.set_value(child.doctype, child.name, key, value);
                            }
        
                            if (key !== "free_item_data") {
                                if (child.apply_rule_on_other_items && JSON.parse(child.apply_rule_on_other_items).length) {
                                    if (!in_list(JSON.parse(child.apply_rule_on_other_items), child.item_code)) {
                                        continue;
                                    }
                                }
        
                                frappe.model.set_value(child.doctype, child.name, key, value);
                            }
                        }
                    }
        
                    frappe.model.round_floats_in(
                        frappe.get_doc(child.doctype, child.name),
                        ["price_list_rate", "discount_percentage"],
                    );
        
                    // if pricing rule set as blank from an existing value, apply price_list
                    if (!this.frm.doc.ignore_pricing_rule && existing_pricing_rule && !child.pricing_rules) {
                        this.apply_price_list(frappe.get_doc(child.doctype, child.name));
                    } else if (!child.pricing_rules) {
                        this.remove_pricing_rule(frappe.get_doc(child.doctype, child.name));
                    }
        
                    if (child.free_item_data && child.free_item_data.length > 0) {
                        this.apply_product_discount(child);
                    }
        
                    if (child.apply_rule_on_other_items && JSON.parse(child.apply_rule_on_other_items).length) {
                        items_rule_dict[child.name] = child;
                    }
                }
        
                this.apply_rule_on_other_items(items_rule_dict);
                this.calculate_taxes_and_totals();
            }

            apply_price_list(item, reset_plc_conversion) {
                // We need to reset plc_conversion_rate sometimes because the call to
                // `erpnext.stock.get_item_details.apply_price_list` is sensitive to its value
        
        
                if (this.frm.doc.doctype === "Material Request") {
                    return;
                }
        
                if (!reset_plc_conversion) {
                    this.frm.set_value("plc_conversion_rate", "");
                }
        
                let me = this;
                let args = this._get_args(item);
                if (!((args.items && args.items.length) || args.price_list)) {
                    return;
                }
        
                if (me.in_apply_price_list == true) return;
        
                me.in_apply_price_list = true;
                return this.frm.call({
                    method: "erpnext.stock.get_item_details.apply_price_list",
                    args: {	args: args, doc: me.frm.doc },
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.run_serially([
                                () => {
                                    if (r.message.parent.price_list_currency)
                                        me.frm.set_value("price_list_currency", r.message.parent.price_list_currency);
                                },
                                () => {
                                    if (r.message.parent.plc_conversion_rate)
                                        me.frm.set_value("plc_conversion_rate", r.message.parent.plc_conversion_rate);
                                },
                                () => {
                                    if(args.items.length) {
                                        me._set_values_for_item_list(r.message.children);
                                        // $.each(r.message.children || [], function(i, d) {
                                        //     me.apply_discount_on_item(d, d.doctype, d.name, 'discount_percentage');
                                        // });
                                    }
                                },
                                () => { me.in_apply_price_list = false; }
                            ]);
        
                        } else {
                            me.in_apply_price_list = false;
                        }
                    }
                }).always(() => {
                    me.in_apply_price_list = false;
                });
            }

            get_rebate_account(doc){
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
                            transaction_type: doc.transaction_type,
                        },
                        callback: function (r) {
                            if (r.message) {
                                frappe.run_serially([
                                    () => {
                                        for (const [key, value] of Object.entries(r.message)) {
                                            if (key !== "price_list_rate") {
                                                me.frm.set_value(key, value)
                                            }
                                        }
                                    },
                                    () => {
                                        if(r.message.selling_price_list != me.frm.doc.selling_price_list){
                                            me.frm.set_value("selling_price_list", r.message.selling_price_list)
                                            return;
                                        }

                                        me.apply_price_list();
                                        me.set_dynamic_labels();
                                    },
                                ]);
                            }
                        },
                    });
                }
            }

            is_a_mapped_document(item) {
                const mapped_item_field_map = {
                    "Delivery Note": ["si_detail", "so_detail", "dn_detail"],
                    "Sales Invoice": ["dn_detail", "so_detail", "sales_invoice_item"],
                    "Purchase Receipt": ["purchase_order_item", "purchase_invoice_item", "purchase_receipt_item"],
                    "Purchase Invoice": ["purchase_order_item", "pr_detail", "po_detail"],
                    "Sales Order": ["prevdoc_docname", "quotation_item", "custom_pre_order_item"],
                    "Purchase Order": ["supplier_quotation_item"],
                };
                const mappped_fields = mapped_item_field_map[this.frm.doc.doctype] || [];
        
                if (item) {
                    return mappped_fields
                        .map((field) => item[field])
                        .filter(Boolean).length > 0;
                } else if (this.frm.doc?.items) {
                    let first_row = this.frm.doc.items[0];
                    if (!first_row) {
                        return false
                    };
        
                    let mapped_rows = mappped_fields.filter(d => first_row[d])
        
                    return mapped_rows?.length > 0;
                }
            }

            change_form_labels(company_currency) {
                let me = this;
        
                this.frm.set_currency_labels(["base_total", "base_net_total", "base_total_taxes_and_charges",
                    "base_discount_amount", "base_grand_total", "base_rounded_total", "base_in_words",
                    "base_taxes_and_charges_added", "base_taxes_and_charges_deducted", "total_amount_to_pay",
                    "base_paid_amount", "base_write_off_amount", "base_change_amount", "base_operating_cost",
                    "base_raw_material_cost", "base_total_cost", "base_scrap_material_cost",
                    "base_rounding_adjustment", "base_rebate_total"], company_currency);
        
                this.frm.set_currency_labels(["total", "net_total", "total_taxes_and_charges", "discount_amount",
                    "grand_total", "taxes_and_charges_added", "taxes_and_charges_deducted","tax_withholding_net_total",
                    "rounded_total", "in_words", "paid_amount", "write_off_amount", "operating_cost",
                    "scrap_material_cost", "rounding_adjustment", "raw_material_cost",
                    "total_cost", "rebate_total"], this.frm.doc.currency);
        
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
                var me = this

                this.frm.set_currency_labels([
                    "base_rate", "base_net_rate", "base_price_list_rate",
                    "base_amount", "base_net_amount", "base_rate_with_margin", "base_rebate_amount"
                ], company_currency, "items");
        
                this.frm.set_currency_labels([
                    "rate", "net_rate", "price_list_rate", "amount",
                    "net_amount", "stock_uom_rate", "rate_with_margin", "rebate_amount"
                ], this.frm.doc.currency, "items");
                
                // toggle columns
		        var item_grid = this.frm.fields_dict["items"].grid;
                $.each(["rebate", "discount_percentage"], function(i, fname) {
                    if(frappe.meta.get_docfield(item_grid.doctype, fname))
                        item_grid.toggle_enable(fname, !me.frm.doc.is_rebate_fixed);
                });
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
                    me.frm.doc.base_rebate_total += item.base_rebate_amount;
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