app_name = "culinary_portal"
app_title = "Culinary Portal"
app_publisher = "culinary"
app_description = "culinary Portal"
app_email = "culinary@gmail.com"
app_license = "mit"

# Apps
# ------------------

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Culinary Portal"]]},
    # {"dt": "Client Script", "filters": [["module", "=", "Culinary Portal"]]},
    # {"dt": "Item Group"},
    # {"dt": "Item"},
    # {"dt": "Supplier"},
    # {"dt": "Customer"},
]

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "culinary_portal",
# 		"logo": "/assets/culinary_portal/logo.png",
# 		"title": "Culinary Portal",
# 		"route": "/culinary_portal",
# 		"has_permission": "culinary_portal.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/culinary_portal/css/culinary_portal.css"
# app_include_js = "/assets/culinary_portal/js/culinary_portal.js"

# include js, css files in header of web template
# web_include_css = "/assets/culinary_portal/css/culinary_portal.css"
# web_include_js = "/assets/culinary_portal/js/culinary_portal.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "culinary_portal/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

doctype_js = {
	"Item": "public/js/item.js",
	"Supplier": "public/js/supplier.js",
	"Agreement": "public/js/agreement.js",
	# "Customer": "public/js/customer.js"
}

doctype_list_js = {
	"Supplier": "public/js/supplier_list.js",
	"Sales Order": "public/js/sales_order_list.js",
}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "culinary_portal/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "culinary_portal.utils.jinja_methods",
# 	"filters": "culinary_portal.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "culinary_portal.install.before_install"
# after_install = "culinary_portal.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "culinary_portal.uninstall.before_uninstall"
# after_uninstall = "culinary_portal.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "culinary_portal.utils.before_app_install"
# after_app_install = "culinary_portal.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "culinary_portal.utils.before_app_uninstall"
# after_app_uninstall = "culinary_portal.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "culinary_portal.notifications.get_notification_config"

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

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

doc_events = {
	"Item": {
		# "after_insert": "culinary_portal.custom_hooks.create_item.handle_item_saved",
		"on_update": [
			# "culinary_portal.custom_hooks.create_item.handle_item_saved",
			"culinary_portal.custom_hooks.create_item.handle_zero_rate_tax_class",
		],
		"on_trash": "culinary_portal.custom_hooks.delete_item.handle_item_deleted",
	},
	"Item Price": {
		# "after_insert": "culinary_portal.custom_hooks.create_item.handle_item_saved",
		"on_update": "culinary_portal.custom_hooks.create_item.handle_item_saved",
	},
	"Item Group": {
		"on_update": "culinary_portal.custom_hooks.create_category.handle_item_group_after_insert",
		"after_rename": "culinary_portal.custom_hooks.create_category.handle_item_group_after_insert",
		"on_trash": "culinary_portal.custom_hooks.create_category.handle_item_group_on_trash",
	},
	"Supplier": {
		"on_update": "culinary_portal.custom_hooks.sync_supplier.handle_supplier_sync",
		"after_rename": "culinary_portal.custom_hooks.sync_supplier.handle_supplier_sync",
		"on_trash": "culinary_portal.custom_hooks.sync_supplier.handle_supplier_on_trash",
	},
	"Customer": {
		"validate": "culinary_portal.custom_hooks.create_b2b_group.handle_customer_status_by_role",
		"before_save": "culinary_portal.custom_hooks.create_agreement.create_agreements_for_customer",
		"after_insert": "culinary_portal.custom_hooks.create_agreement.create_agreements_for_customer_after_insert",
		"on_update": [
			"culinary_portal.custom_hooks.create_b2b_group.handle_customer_role_sync",
			"culinary_portal.custom_hooks.create_b2b_group.handle_customer_b2b_group",
			"culinary_portal.custom_hooks.create_b2b_group.handle_customer_wordpress_sync",
			"culinary_portal.custom_hooks.create_agreement.create_agreements_for_customer_on_update",
			"culinary_portal.custom_hooks.attach_customer_files.attach_customer_files_on_update",
		],
		"on_trash": "culinary_portal.custom_hooks.create_b2b_group.handle_customer_on_trash",
	},
	"Address": {
		"on_update": "culinary_portal.custom_hooks.create_b2b_group.handle_address_wordpress_sync",
	},
	"Agreement": {
		"validate": "culinary_portal.custom_hooks.handle_agreement.handle_agreement_before_submit",
		# "on_submit": "culinary_portal.custom_hooks.handle_agreement.handle_agreement_saved",
		"on_cancel": "culinary_portal.custom_hooks.handle_agreement.handle_agreement_cancelled",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"culinary_portal.tasks.all"
# 	],
# 	"daily": [
# 		"culinary_portal.tasks.daily"
# 	],
# 	"hourly": [
# 		"culinary_portal.tasks.hourly"
# 	],
# 	"weekly": [
# 		"culinary_portal.tasks.weekly"
# 	],
# 	"monthly": [
# 		"culinary_portal.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "culinary_portal.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "culinary_portal.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "culinary_portal.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["culinary_portal.utils.before_request"]
# after_request = ["culinary_portal.utils.after_request"]

# Job Events
# ----------
# before_job = ["culinary_portal.utils.before_job"]
# after_job = ["culinary_portal.utils.after_job"]

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
# 	"culinary_portal.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

