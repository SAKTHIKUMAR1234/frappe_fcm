import frappe
from frappe.utils import cint

from frappe_fcm import devices, notifications, tracking
from frappe_fcm.push import MESSAGE_LOG

MAX_PAGE_LENGTH = 100


@frappe.whitelist(methods=["POST"])
def register_device(
	token: str, platform: str | None = None, app_name: str | None = None, app_version: str | None = None
) -> str:
	"""Get pushes on this device for the session user. Returns the device name."""
	return devices.register_device(frappe.session.user, token, platform, app_name, app_version)


@frappe.whitelist(methods=["POST"])
def remove_device(token: str):
	"""Stop pushes to the session user's device of `token`. A device of another user is refused."""
	owner = frappe.db.get_value(devices.DEVICE, {"token": token}, "user")
	if owner and owner != frappe.session.user:
		frappe.throw(frappe._("This device belongs to another user."), frappe.PermissionError)
	devices.remove_device(token)


@frappe.whitelist(methods=["GET"])
def get_notifications(app_name: str | None = None, start: int = 0, page_length: int = 20) -> list[dict]:
	"""The session user's notifications, newest first."""
	return notifications.get_notifications(
		frappe.session.user, app_name, start=cint(start), page_length=min(cint(page_length), MAX_PAGE_LENGTH)
	)


@frappe.whitelist(methods=["POST"])
def mark_read(name: str | None = None, app_name: str | None = None):
	"""Mark the session user's notification `name` read, or all unread ones without a name."""
	notifications.mark_read(frappe.session.user, name, app_name)


@frappe.whitelist(methods=["GET", "POST"])
def report_event(message_id: str, event: str):
	"""Record that the session user's message was `delivered` or `opened`. `message_id` is the push data
	`fcm_message`, or the FCM message id. A message of another user is refused. GET is allowed because the
	web push service worker has no CSRF token."""
	tracking.report_event(frappe.session.user, message_id, event)
	# Frappe commits a GET request only with this flag.
	frappe.flags.commit = True


@frappe.whitelist(methods=["GET"])
def get_message_counts(filters: str | list | None = None) -> dict:
	"""The number of messages sent, delivered, opened and failed, of the FCM Message Logs of `filters`."""
	frappe.has_permission(MESSAGE_LOG, "read", throw=True)
	return tracking.get_message_counts(frappe.parse_json(filters) if filters else None)


def has_app_permission() -> bool:
	"""Show the app on the apps screen to users who may open FCM Settings."""
	return frappe.has_permission("FCM Settings", "write")
