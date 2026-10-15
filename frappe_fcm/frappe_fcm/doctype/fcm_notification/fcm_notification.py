# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

from functools import partial

import frappe
from frappe.model.document import Document

from frappe_fcm.notifications import publish_notification


class FCMNotification(Document):
	def after_insert(self):
		"""Push the notification and publish its Socket.IO event after commit. A migrated row sets
		`flags.skip_push` and gets neither."""
		if self.flags.skip_push:
			return

		frappe.enqueue(
			"frappe_fcm.notifications.push_notification",
			queue="short",
			enqueue_after_commit=True,
			name=self.name,
		)
		frappe.db.after_commit.add(partial(publish_notification, self.name))


def is_manager(user: str) -> bool:
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def get_permission_query_conditions(user: str | None = None) -> str | None:
	"""Users other than a System Manager see only their own notifications."""
	user = user or frappe.session.user
	if not is_manager(user):
		return f"`tabFCM Notification`.user = {frappe.db.escape(user)}"


def has_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	user = user or frappe.session.user
	return is_manager(user) or doc.user == user
