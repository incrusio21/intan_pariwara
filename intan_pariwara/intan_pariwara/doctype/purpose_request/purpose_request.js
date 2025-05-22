// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

intan_pariwara.purpose = {
    setup_fieldname_select: function (frm) {
        // get the doctype to update fields
		if (!frm.doc.qr_code_reference) return;

        frappe.model.with_doctype(frm.doc.qr_code_reference, function () {
			let get_select_options = function (df, parent_field) {
				// Append parent_field name along with fieldname for child table fields
				let select_value = parent_field ? df.fieldname + "," + parent_field : df.fieldname;

				return {
					value: select_value,
					label: df.fieldname + " (" + __(df.label, null, df.parent) + ")",
				};
			};

			let fields = frappe.get_doc("DocType", frm.doc.qr_code_reference).fields;
			let options = $.map(fields, function (d) {
				return frappe.model.no_value_type.includes(d.fieldtype)
					? null
					: get_select_options(d);
			});

            frm.fields_dict.reference.grid.update_docfield_property("ref_fieldname", "options", options);
		});
    }
}

frappe.ui.form.on("Purpose Request", {
	refresh(frm) {
        intan_pariwara.purpose.setup_fieldname_select(frm);
	},

    qr_code_reference(frm){
        frappe.run_serially([
            () => frm.clear_table("reference"),
            () => intan_pariwara.purpose.setup_fieldname_select(frm)
        ])
    },
});
