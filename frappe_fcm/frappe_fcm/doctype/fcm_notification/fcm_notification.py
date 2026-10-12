# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FCMNotification(Document):
	def after_insert(self):
		"""Push the notification after commit. A migrated row sets `flags.skip_push`."""
		if not self.flags.skip_push:
			frappe.enqueue(
				"frappe_fcm.notifications.push_notification",
				queue="short",
				enqueue_after_commit=True,
				name=self.name,
			)


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
