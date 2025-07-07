$.extend(frappe.ui.form.States.prototype, {
    show_actions() {
		var added = false;
		var me = this;

		// if the loaded doc is dirty, don't show workflow buttons
		if (this.frm.doc.__unsaved === 1) {
			return;
		}

        const scroll_to = (fieldname) => {
            me.frm.scroll_to_field(fieldname);
            me.frm.scroll_set = true;
        };

        var check_mandatory = function (frm) {
            var has_errors = false;
            frm.scroll_set = false;

            if (frm.doc.docstatus == 2) return true; // don't check for cancel

            $.each(frappe.model.get_all_docs(frm.doc), function (i, doc) {
                var error_fields = [];
                var folded = false;

                $.each(frappe.meta.docfield_list[doc.doctype] || [], function (i, docfield) {
                    if (docfield.fieldname) {
                        const df = frappe.meta.get_docfield(doc.doctype, docfield.fieldname, doc.name);

                        if (df.fieldtype === "Fold") {
                            folded = frm.layout.folded;
                        }

                        if (
                            is_docfield_mandatory(doc, df) &&
                            !frappe.model.has_value(doc.doctype, doc.name, df.fieldname)
                        ) {
                            has_errors = true;
                            error_fields[error_fields.length] = __(df.label, null, df.parent);
                            // scroll to field
                            if (!frm.scroll_set) {
                                scroll_to(doc.parentfield || df.fieldname);
                            }

                            if (folded) {
                                frm.layout.unfold();
                                folded = false;
                            }
                        }
                    }
                });

                if (frm.is_new() && frm.meta.autoname === "Prompt" && !frm.doc.__newname) {
                    has_errors = true;
                    error_fields = [__("Name"), ...error_fields];
                }

                if (error_fields.length) {
                    let meta = frappe.get_meta(doc.doctype);
                    let message;
                    if (meta.istable) {
                        const table_field = frappe.meta.docfield_map[doc.parenttype][doc.parentfield];

                        const table_label = __(
                            table_field.label || frappe.unscrub(table_field.fieldname)
                        ).bold();

                        message = __("Mandatory fields required in table {0}, Row {1}", [
                            table_label,
                            doc.idx,
                        ]);
                    } else {
                        message = __("Mandatory fields required in {0}", [__(doc.doctype)]);
                    }
                    message = message + "<br><br><ul><li>" + error_fields.join("</li><li>") + "</ul>";
                    frappe.msgprint({
                        message: message,
                        indicator: "red",
                        title: __("Missing Fields"),
                    });
                    frm.refresh();
                }
            });

            return !has_errors;
        };

        let is_docfield_mandatory = function (doc, df) {
            if (df.reqd) return true;
            if (!df.mandatory_depends_on || !doc) return;

            let out = null;
            let expression = df.mandatory_depends_on;
            let parent = frappe.get_meta(df.parent);

            if (typeof expression === "boolean") {
                out = expression;
            } else if (typeof expression === "function") {
                out = expression(doc);
            } else if (expression.substr(0, 5) == "eval:") {
                try {
                    out = frappe.utils.eval(expression.substr(5), { doc, parent });
                    if (parent && parent.istable && expression.includes("is_submittable")) {
                        out = true;
                    }
                } catch (e) {
                    frappe.throw(__('Invalid "mandatory_depends_on" expression'));
                }
            } else {
                var value = doc[expression];
                if ($.isArray(value)) {
                    out = !!value.length;
                } else {
                    out = !!value;
                }
            }

            return out;
        };

		function has_approval_access(transition) {
			let approval_access = false;
			const user = frappe.session.user;
			if (
				user === "Administrator" ||
				transition.allow_self_approval ||
				user !== me.frm.doc.owner
			) {
				approval_access = true;
			}
			return approval_access;
		}

        function run_action(d, reason){
            // set the workflow_action for use in form scripts
            if(check_mandatory(me.frm)){
                frappe.dom.freeze();
                me.frm.selected_workflow_action = d.action;
                me.frm.script_manager.trigger("before_workflow_action").then(() => {
                    frappe
                        .xcall("frappe.model.workflow.apply_workflow", {
                            doc: me.frm.doc,
                            action: d.action,
                            reason: reason
                        })
                        .then((doc) => {
                            frappe.model.sync(doc);
                            me.frm.refresh();
                            me.frm.selected_workflow_action = null;
                            me.frm.script_manager.trigger("after_workflow_action");
                        })
                        .finally(() => {
                            frappe.dom.unfreeze();
                        });
                });
            }
        }
        
		frappe.workflow.get_transitions(this.frm.doc).then((transitions) => {
			this.frm.page.clear_actions_menu();
			transitions.forEach((d) => {
				if (frappe.user_roles.includes(d.allowed) && has_approval_access(d)) {
					added = true;
					me.frm.page.add_action_item(__(d.action), function () {
                        if(d.reason && !d.same_reason){
                            var dialog = new frappe.ui.Dialog({
                                title: __(`${d.action} Reason`),
                                fields: [
                                    {
                                        label: `Reason`,
                                        fieldname: "reason",
                                        fieldtype: d.reason_type,
                                        options: d.master_reason,
                                        reqd: 1,
                                    },
                                ],
                                primary_action: function () {
                                    var data = dialog.get_values();
                                    run_action(d, data.reason)

                                    dialog.hide();
                                },
                                primary_action_label: __("Submit"),
                            });
                            dialog.show();
                        }else{
                            run_action(d)
                        }
					});
				}
			});

			this.setup_btn(added);
		});
	}
})