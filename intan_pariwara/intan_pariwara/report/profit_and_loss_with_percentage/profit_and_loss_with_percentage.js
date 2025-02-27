// Copyright (c) 2025, DAS and contributors
// For license information, please see license.txt

frappe.query_reports["Profit and Loss with Percentage"] = $.extend({}, erpnext.financial_statements);

erpnext.utils.add_dimensions("Profit and Loss with Percentage", 10);

frappe.query_reports["Profit and Loss with Percentage"]["filters"].push({
	fieldname: "selected_view",
	label: __("Select View"),
	fieldtype: "Select",
	options: [
		{ value: "Report", label: __("Report View") },
		{ value: "Growth", label: __("Growth View") },
		{ value: "Margin", label: __("Margin View") },
	],
	default: "Report",
	reqd: 1,
});

frappe.query_reports["Profit and Loss with Percentage"]["filters"].push({
	fieldname: "accumulated_values",
	label: __("Accumulated Values"),
	fieldtype: "Check",
	default: 1,
});

frappe.query_reports["Profit and Loss with Percentage"]["filters"].push({
	fieldname: "include_default_book_entries",
	label: __("Include Default FB Entries"),
	fieldtype: "Check",
	default: 1,
});

frappe.query_reports["Profit and Loss with Percentage"]["formatter"] = function (value, row, column, data, default_formatter) {
	let new_column = Object.assign({}, column);
	if(in_list(["'Percentage Profit for the year'"], data.account) && column.fieldtype == "Currency"){
		new_column.fieldtype = "Percent"
	}

	value = default_formatter(value, row, new_column, data);
	
	return value
}