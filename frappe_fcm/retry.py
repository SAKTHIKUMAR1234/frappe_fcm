"""Durable notification retries; uncertain sends are never replayed automatically."""

import hashlib
import json

import frappe
from frappe.utils import add_to_date, now_datetime

from frappe_fcm.client import FCMError, get_client
from frappe_fcm.devices import get_enabled_devices, remove_device
from frappe_fcm.push import send

NOTIFICATION = "FCM Notification"
MAX_ATTEMPTS = 5
BATCH_SIZE = 100


def retry_notifications():
	"""Queue a bounded batch every two minutes; the worker claims each row."""
	for name in frappe.get_all(
		NOTIFICATION,
		filters={"delivery_status": ("in", ["Pending", "Failed"]), "attempts": ("<", MAX_ATTEMPTS)},
		or_filters=[["next_retry", "<=", now_datetime()], ["next_retry", "is", "not set"]],
		pluck="name",
		order_by="modified asc",
		limit_page_length=BATCH_SIZE,
	):
		frappe.enqueue("frappe_fcm.notifications.push_notification", name=name, queue="short")


def claim(name):
	"""Commit ownership before any network call. A crashed claim requires review."""
	rows = frappe.db.sql(
		"select delivery_status, attempts, next_retry from `tabFCM Notification` where name=%s for update",
		(name,),
		as_dict=True,
	)
	if not rows or not is_due(rows[0]):
		frappe.db.commit()
		return False
	frappe.db.set_value(
		NOTIFICATION,
		name,
		{
			"delivery_status": "Processing",
			"attempts": (rows[0].attempts or 0) + 1,
		},
	)
	frappe.db.commit()
	return True


def is_due(row):
	return (
		row.delivery_status in ("Pending", "Failed")
		and (row.attempts or 0) < MAX_ATTEMPTS
		and (not row.next_retry or row.next_retry <= now_datetime())
	)


def deliver(name):
	from frappe_fcm.notifications import get_push

	try:
		doc = frappe.get_doc(NOTIFICATION, name)
	except frappe.DoesNotExistError:
		return
	if not is_due(doc):
		return
	push = get_push(doc)
	devices = get_enabled_devices([doc.user], doc.app_name) if push else []
	client = get_client() if devices else None
	if not client:
		defer(name)
		return
	if not claim(name):
		return
	doc.reload()
	try:
		states = json.loads(doc.delivery_state or "{}")
		for device in devices:
			deliver_device(doc, states, client, push, device)
		finish(doc, result_status(states))
	except Exception:
		# The provider may have accepted the message: replay could duplicate it.
		finish(doc, "Unknown", "Delivery interrupted; review before retrying.")
		frappe.log_error(title="FCM notification delivery")


def deliver_device(doc, states, client, push, device):
	key = hashlib.sha256(device.token.encode()).hexdigest()
	if states.get(key) in ("Sent", "Unknown", "Dead"):
		return
	states[key] = "Unknown"
	persist_states(doc, states)
	try:
		message_id = send(client, push, {"token": device.token}, device.user)
	except FCMError as error:
		states[key] = failure_status(error)
		doc.delivery_error = str(error)
		if error.is_dead_token:
			remove_device(device.token)
	else:
		states[key] = "Sent"
		doc.message_id = doc.message_id or message_id
	persist_states(doc, states)


def failure_status(error):
	if error.is_dead_token:
		return "Dead"
	return "Unknown" if error.code == "DELIVERY_UNKNOWN" else "Failed"


def result_status(states):
	if "Failed" in states.values():
		return "Failed"
	if "Unknown" in states.values():
		return "Unknown"
	return "Sent" if "Sent" in states.values() else "Exhausted"


def persist_states(doc, states):
	frappe.db.set_value(
		NOTIFICATION,
		doc.name,
		{
			"delivery_state": json.dumps(states),
			"message_id": doc.message_id,
			"delivery_error": doc.delivery_error,
		},
	)
	frappe.db.commit()


def finish(doc, status, error=None):
	if status == "Failed" and doc.attempts >= MAX_ATTEMPTS:
		status = "Exhausted"
	frappe.db.set_value(
		NOTIFICATION,
		doc.name,
		{
			"delivery_status": status,
			"delivery_error": error or doc.delivery_error,
			"next_retry": add_to_date(now_datetime(), minutes=2**doc.attempts),
		},
	)
	frappe.db.commit()


def defer(name):
	"""Let other queued notifications progress without spending a send attempt."""
	frappe.db.set_value(NOTIFICATION, name, "next_retry", add_to_date(now_datetime(), minutes=2))
	frappe.db.commit()
