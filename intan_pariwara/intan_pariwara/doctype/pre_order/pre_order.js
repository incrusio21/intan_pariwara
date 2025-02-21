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
		
		frappe.flags.resend_period = 60;
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
					var d = frappe.prompt(
						[
							{
								fieldtype: "Data",
								label: __("One Time Password"),
								fieldname: "otp",
								reqd: 1,
							}
						],
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

					// Tambahkan Resend OTP ke dalam dialog
					const $inputGroup = d.$wrapper.find('[data-fieldname="otp"]').find(".form-group");
					const resend_text = __('Re-send OTP')

					// Buat link Resend OTP
					const $resendLink = $(`
						<a class="resend-otp" href="#" style="cursor: pointer;pointer-events: none;display: block;color: #6c757d;">
							${resend_text}
						</a>
					`);
					
					// Fungsi update teks
					const updateButtonText = (countdown) => {
						$resendLink.text(__('Resent in ') + `${Math.floor(countdown/60)}:${countdown%60 < 10 ? '0' : ''}${countdown%60}`);
					};
					
					// Fungsi untuk memulai countdown
					const startCountdown = () => {
						$resendLink.css({ 'pointer-events': 'none', 'color': '#6c757d' });
						
						// Hentikan interval sebelumnya (jika ada)
						if (frappe.flags.intervalId) clearInterval(frappe.flags.intervalId);

						frappe.flags.intervalId = setInterval(() => {
							frappe.flags.otp_countdown--;
							
							if (frappe.flags.otp_countdown <= 0) {
								clearInterval(frappe.flags.intervalId);
								$resendLink.text(__('Re-send OTP'))
									.css({ 'pointer-events': 'auto', 'color': '#007bff' });
								return;
							}
							
							updateButtonText(frappe.flags.otp_countdown);
						}, 1000);
					};
					
					// Event handler untuk Resend OTP
					$resendLink.on("click", function(e) {
						e.preventDefault();
						
						// Nonaktifkan sementara
						$resendLink.css({ 'pointer-events': 'none', 'color': '#6c757d' });
						frappe.flags.otp_countdown = frappe.flags.resend_period

						frappe.call({
							method: "intan_pariwara.controllers.otp_notification.request_otp_notification", // Ganti dengan method backend Anda
							args: {
								document_type: doc.doctype, 
								document_no: doc.name,
								method: "after_insert"
								// Sesuaikan parameter
							},
							always: function(data) {
								if(!data.exc){
									updateButtonText(frappe.flags.otp_countdown)

									startCountdown()
								}else{
									$resendLink.text(resend_text).css({ 'pointer-events': 'auto', 'color': '#007bff' });
								}
							}
						});

						
						
					});

					if(frappe.flags.otp_countdown){
						startCountdown()
					}else{
						$resendLink.css({ 'pointer-events': 'auto', 'color': '#007bff' });
					}

					// Tambahkan link ke dalam dialog
					$inputGroup.append($resendLink);
				}
			)
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