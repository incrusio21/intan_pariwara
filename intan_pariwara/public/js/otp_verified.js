frappe.provide("intan_pariwara.utils");

intan_pariwara.utils.OtpVerified = class OtpVerified {
    constructor(opts) {
		this.frm = opts.frm;
		frappe.flags.resend_period = 60;
		
		this.make_button_verified(this.frm.doc)
    }

	make_button_verified(doc){
		var me = this;

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
}