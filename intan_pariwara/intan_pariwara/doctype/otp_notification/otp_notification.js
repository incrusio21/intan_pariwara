// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt
frappe.provide("intan_pariwara.notification")

intan_pariwara.notification = {
    setup_fieldname_select: function (frm) {
        // get the doctype to update fields
		if (!frm.doc.document_type) {
			return;
		}

        frappe.model.with_doctype(frm.doc.document_type, function () {
			let get_select_options = function (df, parent_field) {
				// Append parent_field name along with fieldname for child table fields
				let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;

				return {
					value: select_value,
					label: df.fieldname + " (" + __(df.label, null, df.parent) + ")",
				};
			};

			let fields = frappe.get_doc("DocType", frm.doc.document_type).fields;
			let options = $.map(fields, function (d) {
				return frappe.model.no_value_type.includes(d.fieldtype)
					? null
					: get_select_options(d);
			});

            // set value changed options
			frm.set_df_property("field_otp_secret", "options", [""].concat([
                { value: "name", label: `name (${__("Name")})` }
            ]).concat(options));
		});
    }
}

frappe.ui.form.on("OTP Notification", {
	refresh(frm) {
        intan_pariwara.notification.setup_fieldname_select(frm);
	},
    document_type(frm){
        intan_pariwara.notification.setup_fieldname_select(frm);
    }
});
