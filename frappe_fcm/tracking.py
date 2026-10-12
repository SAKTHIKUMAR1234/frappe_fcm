import frappe
from frappe import _
from frappe.utils import now_datetime

from frappe_fcm.push import MESSAGE_LOG

# Event -> the FCM Message Log fields it sets. Opening a message also proves its delivery.
EVENT_FIELDS = {"delivered": ("delivered_on",), "opened": ("delivered_on", "opened_on")}


def report_event(user: str, message_id: str, event: str):
	"""Record that the user's message was delivered or opened. `message_id` is the `fcm_message` value of
	the push data (the log name) or the FCM message id, in full or after `/messages/`. The first time of
	each event is kept. A message of another user is refused."""
	if event not in EVENT_FIELDS:
		frappe.throw(_("Event must be one of: {0}.").format(", ".join(EVENT_FIELDS)))

	log = find_log(message_id)
	if not log:
		frappe.throw(_("Message not found."), frappe.DoesNotExistError)
	if log.user != user:
		frappe.throw(_("This message belongs to another user."), frappe.PermissionError)
	if log.status == "Failed":
		frappe.throw(_("A failed message cannot be {0}.").format(event))

	table = frappe.qb.DocType(MESSAGE_LOG)
	for fieldname in EVENT_FIELDS[event]:
		field = table[fieldname]
		frappe.qb.update(table).set(field, now_datetime()).where(table.name == log.name).where(
			field.isnull()
		).run()


def find_log(message_id: str) -> frappe._dict | None:
	"""`name`, `user` and `status` of the log of a log name or an FCM message id."""
	if not message_id:
		return None
	fields = ["name", "user", "status"]
	return frappe.db.get_value(MESSAGE_LOG, message_id, fields, as_dict=True) or frappe.db.get_value(
		MESSAGE_LOG,
		{"message_id": ("in", [message_id, f"{get_message_prefix()}{message_id}"])},
		fields,
		as_dict=True,
	)


def get_message_prefix() -> str:
	"""The FCM message id without its last part, such as `projects/<project>/messages/`."""
	return f"projects/{frappe.db.get_single_value('FCM Settings', 'project_id')}/messages/"


def get_message_counts(filters: list | None = None) -> dict:
	"""The number of messages sent, delivered, opened and failed, of the logs that match `filters` (list
	filters, such as those of the list view)."""
	filters = filters or []
	return {
		"sent": frappe.db.count(MESSAGE_LOG, [*filters, [MESSAGE_LOG, "status", "=", "Sent"]]),
		"delivered": frappe.db.count(MESSAGE_LOG, [*filters, [MESSAGE_LOG, "delivered_on", "is", "set"]]),
		"opened": frappe.db.count(MESSAGE_LOG, [*filters, [MESSAGE_LOG, "opened_on", "is", "set"]]),
		"failed": frappe.db.count(MESSAGE_LOG, [*filters, [MESSAGE_LOG, "status", "=", "Failed"]]),
	}
