frappe.ui.form.PrintView.prototype.printit = function () {
    let me = this;

    if (cint(me.print_settings.enable_print_server)) {
        if (localStorage.getItem("network_printer")) {
            me.print_by_server();
        } else {
            me.network_printer_setting_dialog(() => me.print_by_server());
        }
    } else if (me.get_mapped_printer().length === 1) {
        // printer is already mapped in localstorage (applies for both raw and pdf )
        if (me.is_raw_printing()) {
            me.get_raw_commands(function (out) {
                frappe.ui.form
                    .qz_connect()
                    .then(function () {
                        let printer_map = me.get_mapped_printer()[0];
                        let data = [out.raw_commands];
                        let config = qz.configs.create(printer_map.printer);
                        return qz.print(config, data);
                    })
                    .then(frappe.ui.form.qz_success)
                    .catch((err) => {
                        frappe.ui.form.qz_fail(err);
                    });
            });
        } else {
            frappe.show_alert(
                {
                    message: __('PDF printing via "Raw Print" is not supported.'),
                    subtitle: __(
                        "Please remove the printer mapping in Printer Settings and try again."
                    ),
                    indicator: "info",
                },
                14
            );
            //Note: need to solve "Error: Cannot parse (FILE)<URL> as a PDF file" to enable qz pdf printing.
        }
    } else if (me.is_raw_printing()) {
        // printer not mapped in localstorage and the current print format is raw printing
        frappe.show_alert(
            {
                message: __("Printer mapping not set."),
                subtitle: __(
                    "Please set a printer mapping for this print format in the Printer Settings"
                ),
                indicator: "warning",
            },
            14
        );
        me.printer_setting_dialog();
    } else {
        const docu = me.frm.doc
        if ("custom_print_counter" in docu) {
            const counter = docu.custom_print_counter + 1;
            frappe.call('intan_pariwara.intan_pariwara.custom.pick_list.print_counter', {
                'doctype': docu.doctype,
                'docname': docu.name,
                counter
            }).then(r => {
                me.frm.doc = r.message
            })
        }

        me.render_page("/printview?", true);

    }
}