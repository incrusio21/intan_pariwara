app_name = "intan_pariwara"
app_title = "Intan Pariwara"
app_publisher = "DAS"
app_description = "DAS"
app_email = "das@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "intan_pariwara",
# 		"logo": "/assets/intan_pariwara/logo.png",
# 		"title": "Intan Pariwara",
# 		"route": "/intan_pariwara",
# 		"has_permission": "intan_pariwara.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "intan_pariwara.bundle.css"
app_include_js = "intan_pariwara.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/intan_pariwara/css/intan_pariwara.css"
# web_include_js = "/assets/intan_pariwara/js/intan_pariwara.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "intan_pariwara/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Customer" : "intan_pariwara/custom/customer.js",
    "Delivery Note" : "intan_pariwara/custom/delivery_note.js",
    "Sales Order" : "intan_pariwara/custom/sales_order.js",
    "Sales Invoice" : "intan_pariwara/custom/sales_invoice.js",
    "Workflow" : "intan_pariwara/custom/workflow.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

fixtures = [
    {
		"dt": "Server Script"
	},
	{
		"dt": "Webhook"
	}
]
# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "intan_pariwara/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

website_route_rules = [
	{"from_route": "/preview-pre-order/<path:app_path>", "to_route": "preview-pre-order"},
]

fixtures = [
    {
		"dt": "Stock Entry Type", 
		"filters": [
            ["name", "in", [
				"Transfer of Promotional Goods",
				]
            ]
		]
	},
]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	# "methods": "intan_pariwara.utils.jinja_methods",
	"filters": [
    	"intan_pariwara.utils.jinja_filters.format_nomor_telepon"
	]
}

# Installation
# ------------

# before_install = "intan_pariwara.install.before_install"
# after_install = "intan_pariwara.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "intan_pariwara.uninstall.before_uninstall"
# after_uninstall = "intan_pariwara.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "intan_pariwara.utils.before_app_install"
# after_app_install = "intan_pariwara.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "intan_pariwara.utils.before_app_uninstall"
# after_app_uninstall = "intan_pariwara.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "intan_pariwara.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Delivery Note": "intan_pariwara.overrides.delivery_note.DeliveryNote",
	"Sales Invoice": "intan_pariwara.overrides.sales_invoice.SalesInvoice",
	"Sales Order": "intan_pariwara.overrides.sales_order.SalesOrder",
	# "Selling Setting": "intan_pariwara.overrides.selling_settings.SellingSettings",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    # doc event untuk nofication otp
	"*": {
		"after_insert": "intan_pariwara.controllers.otp_notification.OtpNotification",
		"on_update": "intan_pariwara.controllers.otp_notification.OtpNotification",
		"on_submit": "intan_pariwara.controllers.otp_notification.OtpNotification",
		"on_cancel": "intan_pariwara.controllers.otp_notification.OtpNotification",
		"on_change": "intan_pariwara.controllers.otp_notification.OtpNotification",
	},
    ("Sales Order", "Delivery Note", "Sales Invoice"): {
        "before_validate": "intan_pariwara.intan_pariwara.custom.selling_event.SellingEvent"
	},
    "Customer": {
		"before_validate": "intan_pariwara.intan_pariwara.custom.customer.disabled_based_account"
	},
    "Delivery Note": {
		"before_validate": "intan_pariwara.intan_pariwara.custom.delivery_note.add_picking_list_to_status_updater",
		"before_cancel": "intan_pariwara.intan_pariwara.custom.delivery_note.add_picking_list_to_status_updater",
	},
    "Sales Invoice": {
        "before_submit": "intan_pariwara.intan_pariwara.custom.sales_invoice.SalesInvoice",
		"on_submit": "intan_pariwara.intan_pariwara.custom.sales_invoice.create_and_delete_rebate",
		"on_cancel": "intan_pariwara.intan_pariwara.custom.sales_invoice.create_and_delete_rebate",
		"on_trash": "intan_pariwara.intan_pariwara.custom.sales_invoice.create_and_delete_rebate"
	},
    "Stock Entry": {
        "on_submit": "intan_pariwara.intan_pariwara.custom.stock_entry.update_plafon_promosi",
	},
    "Workflow": {
        "validate": "intan_pariwara.intan_pariwara.custom.workflow.create_custom_field_for_reason",
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	# "all": [
	# 	"intan_pariwara.tasks.all"
	# ],
	"daily": [
		"intan_pariwara.intan_pariwara.custom.sales_invoice.update_bad_debt_sales_invoice"
	],
	# "hourly": [
	# 	"intan_pariwara.tasks.hourly"
	# ],
	# "weekly": [
	# 	"intan_pariwara.tasks.weekly"
	# ],
	# "monthly": [
	# 	"intan_pariwara.tasks.monthly"
	# ],
}

# Testing
# -------

# before_tests = "intan_pariwara.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"erpnext.selling.doctype.sales_order.sales_order.make_delivery_note": "intan_pariwara.intan_pariwara.custom.sales_order.make_delivery_note",
	"erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice": "intan_pariwara.intan_pariwara.custom.delivery_note.make_sales_invoice",
	"erpnext.stock.get_item_details.apply_price_list": "intan_pariwara.controllers.queries.apply_price_list",
	"frappe.model.workflow.apply_workflow": "intan_pariwara.model.workflow.apply_workflow",
	"frappe.model.workflow.get_transitions": "intan_pariwara.model.workflow.get_transitions",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps

override_doctype_dashboards = {
	"Delivery Note": "intan_pariwara.dashboards.delivery_note.get_data",
	"Sales Order": "intan_pariwara.dashboards.sales_order.get_data",
	"Sales Invoice": "intan_pariwara.dashboards.sales_invoice.get_data",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["intan_pariwara.utils.before_request"]
# after_request = ["intan_pariwara.utils.after_request"]

# Job Events
# ----------
# before_job = ["intan_pariwara.utils.before_job"]
# after_job = ["intan_pariwara.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"intan_pariwara.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

extend_bootinfo = [
	"intan_pariwara.startup.boot.bootinfo",
]