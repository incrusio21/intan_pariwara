// Copyright (c) 2025, DAS and Contributors
// License: GNU General Public License v3. See license.txt

intan_pariwara.utils.Transaction = class Transaction {
	constructor(opts) {
        this.frm = opts.frm;
    }

    default_warehouse(){
        var me = this

        frappe.ui.form.on(this.frm.doctype, "branch", function(frm) {
            if(!frm.doc.branch) return
            me.set_target_warehouse()
        })

        frappe.ui.form.on(this.frm.doctype, "company", function(frm) {
            if(!frm.doc.branch) return
            me.set_target_warehouse()
        })
    }

    set_target_warehouse(){
        var frm = this.frm
        // jika advance skip get warehouse
        if(frm.doc.is_advance) return

        frappe.call({
            method: "intan_pariwara.controllers.queries.get_default_warehouse",
            args:{
                branch: frm.doc.branch,
                company: frm.doc.company,
            },
            callback: function (r) {
                if (r.message) {
                    frappe.run_serially([
                        () => frm.set_value(r.message),
                        () => frm.refresh()
                    ]);
                }
            }
        })
    }
}