// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

intan_pariwara.workflow = {
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
			frm.set_df_property("insert_after_field", "options", [""].concat(options));

            if(!frm.doc.insert_after_field && options.find(d => d.value === "amended_from")){
                frm.set_value("insert_after_field", "amended_from")
            }
		});
    }
}

frappe.ui.form.on("Workflow", {
	refresh(frm) {
        intan_pariwara.workflow.setup_fieldname_select(frm);
	},
    document_type(frm){
        frappe.run_serially([
            () => frm.set_value("insert_after_field", ""),
            () => intan_pariwara.workflow.setup_fieldname_select(frm)
        ])
    }
});