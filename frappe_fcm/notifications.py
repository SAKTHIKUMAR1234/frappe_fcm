import json

import frappe
from frappe import _

from frappe_fcm.push import Push, deliver_to_users

NOTIFICATION = "FCM Notification"
FIELDS = ("name", "title", "body", "data", "read", "creation", "reference_doctype", "reference_name")


def notify(user: str, title: str, body: str, data: dict | None = None, app_name: str | None = None, **values):
	"""Add a notification to the user's inbox; it is pushed to the user's devices after commit. `values`
	sets other fields, such as `reference_doctype` or an app's custom field."""
	return frappe.get_doc(
		{
			"doctype": NOTIFICATION,
			"user": user,
			"title": title,
			"body": body,
			"data": json.dumps(data) if data else None,
			"app_name": app_name,
			**values,
		}
	).insert(ignore_permissions=True)


def push_notification(name: str):
	"""Push the notification to the user's enabled devices of its app and keep the first message id.
	The app's `fcm_push` hook builds the push and can skip it."""
	try:
		doc = frappe.get_doc(NOTIFICATION, name)
	except frappe.DoesNotExistError:
		# The inbox row can be deleted while its after-commit job is waiting.
		return
	push = get_push(doc)
	message_ids = deliver_to_users([doc.user], push, doc.app_name) if push else []
	if message_ids:
		frappe.db.set_value(NOTIFICATION, name, "message_id", message_ids[0], update_modified=False)


def get_push(doc) -> Push | None:
	"""The push of a notification. The hook `fcm_push = {app_name: "dotted.path"}` gives a function
	`(doc) -> Push | None`; None sends nothing. Without a hook, the data carries the notification name."""
	builders = frappe.get_hooks("fcm_push", {}).get(doc.app_name)
	if builders:
		return frappe.get_attr(builders[-1])(doc)
	return Push(doc.title, doc.body or "", {**get_data(doc), "notification": doc.name})


def get_data(row) -> dict:
	"""The `data` JSON of a row or document as a dict; empty when not set."""
	return json.loads(row.data) if isinstance(row.data, str) and row.data else row.data or {}


def get_filters(user: str, app_name: str | None, filters: dict | None = None) -> dict:
	"""The user's rows, of `app_name` when given."""
	filters = {**(filters or {}), "user": user}
	if app_name:
		filters["app_name"] = app_name
	return filters


def get_notifications(
	user: str,
	app_name: str | None = None,
	filters: dict | None = None,
	start: int = 0,
	page_length: int = 20,
	fields: tuple = FIELDS,
) -> list[frappe._dict]:
	"""The user's notifications of `app_name`, newest first. Read with `frappe.get_list`, so the row rule
	applies to the session user."""
	return frappe.get_list(
		NOTIFICATION,
		filters=get_filters(user, app_name, filters),
		fields=list(fields),
		order_by="creation desc, name desc",
		offset=start,
		limit=page_length,
	)


def count_notifications(user: str, app_name: str | None = None, filters: dict | None = None) -> int:
	return frappe.db.count(NOTIFICATION, get_filters(user, app_name, filters))


def mark_read(user: str, name: str | None = None, app_name: str | None = None):
	"""Mark the user's notification `name` read, or all unread ones without a name. A notification of
	another user or app is "not found"."""
	filters = get_filters(user, app_name)
	if name and not frappe.db.exists(NOTIFICATION, {**filters, "name": name}):
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	if name:
		filters["name"] = name
	frappe.db.set_value(NOTIFICATION, {**filters, "read": 0}, "read", 1, update_modified=False)


def find_by_message_id(user: str, message_id: str, app_name: str | None = None) -> str | None:
	"""The user's notification of a push message id; a notification without a push is known by name."""
	filters = get_filters(user, app_name)
	return frappe.db.get_value(NOTIFICATION, {**filters, "message_id": message_id}) or frappe.db.get_value(
		NOTIFICATION, {**filters, "name": message_id}
	)
