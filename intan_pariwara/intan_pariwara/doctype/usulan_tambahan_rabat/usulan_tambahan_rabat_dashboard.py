# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

from frappe import _

def get_data():
	return {
		"fieldname": "sales_order",
		"internal_links": {
			"Sales Order": "sales_order",
		},
		"transactions": [
			{"label": _("Reference"), "items": ["Sales Order"]},
		],
	}