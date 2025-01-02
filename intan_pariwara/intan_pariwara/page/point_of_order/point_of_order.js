frappe.provide("erpnext.PointOfOrder");

frappe.pages['point-of-order'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Point of Order"),
		single_column: true,
	});

	frappe.require("point-of-order.bundle.js", function () {
		wrapper.pos = new erpnext.PointOfOrder.Controller(wrapper);
		window.cur_pos = wrapper.pos;
	});
}

frappe.pages["point-of-order"].refresh = function (wrapper) {
	if (document.scannerDetectionData) {
		onScan.detachFrom(document);
		wrapper.pos.wrapper.html("");
		wrapper.pos.check_opening_entry();
	}
};