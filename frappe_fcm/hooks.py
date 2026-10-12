app_name = "frappe_fcm"
app_title = "Frappe FCM"
app_publisher = "Essdee"
app_description = "Firebase Cloud Messaging push for Frappe"
app_email = "anas@essdee.fit"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

app_logo_url = "/assets/frappe_fcm/images/frappe-fcm-logo.svg"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": "/desk/fcm-settings",
		"has_permission": "frappe_fcm.api.has_app_permission",
	}
]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `frappe_fcm/dock/frappe_fcm/frappe_fcm.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/frappe_fcm/css/frappe_fcm.css"
# app_include_js = "/assets/frappe_fcm/js/frappe_fcm.js"

# include js, css files in header of web template
# web_include_css = "/assets/frappe_fcm/css/frappe_fcm.css"
# web_include_js = "/assets/frappe_fcm/js/frappe_fcm.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "frappe_fcm/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "frappe_fcm/public/icons.svg"

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

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "frappe_fcm.utils.jinja_methods",
# 	"filters": "frappe_fcm.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "frappe_fcm.install.before_install"
# after_install = "frappe_fcm.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "frappe_fcm.uninstall.before_uninstall"
# after_uninstall = "frappe_fcm.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "frappe_fcm.utils.before_app_install"
# after_app_install = "frappe_fcm.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "frappe_fcm.utils.before_app_uninstall"
# after_app_uninstall = "frappe_fcm.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "frappe_fcm.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "frappe_fcm.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["frappe_fcm.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

_NOTIFICATION = "frappe_fcm.frappe_fcm.doctype.fcm_notification.fcm_notification"
permission_query_conditions = {"FCM Notification": f"{_NOTIFICATION}.get_permission_query_conditions"}
has_permission = {"FCM Notification": f"{_NOTIFICATION}.has_permission"}

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

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"frappe_fcm.tasks.all"
# 	],
# 	"daily": [
# 		"frappe_fcm.tasks.daily"
# 	],
# 	"hourly": [
# 		"frappe_fcm.tasks.hourly"
# 	],
# 	"weekly": [
# 		"frappe_fcm.tasks.weekly"
# 	],
# 	"monthly": [
# 		"frappe_fcm.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "frappe_fcm.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "frappe_fcm.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "frappe_fcm.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "frappe_fcm.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["frappe_fcm.utils.before_request"]
# after_request = ["frappe_fcm.utils.after_request"]

# Job Events
# ----------
# before_job = ["frappe_fcm.utils.before_job"]
# after_job = ["frappe_fcm.utils.after_job"]

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
# 	"frappe_fcm.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

default_log_clearing_doctypes = {"FCM Message Log": 30}

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
