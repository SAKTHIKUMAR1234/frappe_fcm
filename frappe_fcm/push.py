import json
from dataclasses import dataclass

import frappe

from frappe_fcm.client import FCMClient, FCMError, get_client
from frappe_fcm.devices import get_enabled_devices, remove_device

MESSAGE_LOG = "FCM Message Log"


@dataclass(frozen=True)
class Push:
	"""One push. `data_only` sends no `notification` block: title and body go in `data`, and the app
	shows the push itself. `collapse_key` lets Android keep only the latest undelivered push."""

	title: str
	body: str
	data: dict | None = None
	data_only: bool = False
	collapse_key: str | None = None

	def get_message(self, target: dict) -> dict:
		"""The HTTP v1 message for `target` (`{"token": ...}` or `{"topic": ...}`). Data values are text."""
		data = {
			key: value if isinstance(value, str) else json.dumps(value)
			for key, value in (self.data or {}).items()
		}
		message = {**target, "data": data}
		if self.data_only:
			message["data"] = {"title": self.title, "body": self.body, **data}
		else:
			message["notification"] = {"title": self.title, "body": self.body}
		if self.collapse_key:
			message["android"] = {"collapse_key": self.collapse_key}
		return message


def send_to_users(
	users: list[str],
	title: str,
	body: str,
	data: dict | None = None,
	app_name: str | None = None,
	*,
	data_only: bool = False,
	collapse_key: str | None = None,
):
	"""Queue a push to the enabled devices of `users` (of `app_name` when given) after commit."""
	frappe.enqueue(
		"frappe_fcm.push.deliver_to_users",
		queue="short",
		enqueue_after_commit=True,
		users=list(users),
		push=Push(title, body, data, data_only, collapse_key),
		app_name=app_name,
	)


def send_to_topic(
	topic: str,
	title: str,
	body: str,
	data: dict | None = None,
	*,
	data_only: bool = False,
	collapse_key: str | None = None,
):
	"""Queue a push to the subscribers of `topic` after commit."""
	frappe.enqueue(
		"frappe_fcm.push.deliver_to_topic",
		queue="short",
		enqueue_after_commit=True,
		topic=topic,
		push=Push(title, body, data, data_only, collapse_key),
	)


def deliver_to_users(users: list[str], push: Push, app_name: str | None = None) -> list[str]:
	"""Send `push` now to each enabled device of `users` and return the message ids. A device whose token
	FCM reports dead (`FCMError.is_dead_token`) is deleted."""
	devices = get_enabled_devices(users, app_name)
	client = get_client() if devices else None
	if not client:
		return []

	message_ids = []
	for device in devices:
		try:
			message_ids.append(send(client, push, {"token": device.token}, device.user))
		except FCMError as error:
			if error.is_dead_token:
				remove_device(device.token)
	return message_ids


def deliver_to_topic(topic: str, push: Push) -> str | None:
	"""Send `push` now to `topic`; the message id, or None when it failed."""
	client = get_client()
	if not client:
		return None
	try:
		return send(client, push, {"topic": topic})
	except FCMError:
		return None


def send(client: FCMClient, push: Push, target: dict, user: str | None = None) -> str:
	"""Send one message and write its FCM Message Log; a failure is logged and raised."""
	log = frappe.new_doc(
		MESSAGE_LOG,
		target=next(iter(target.values())),
		user=user,
		title=push.title,
		body=push.body,
		data=json.dumps(push.data or {}),
	)
	try:
		log.message_id = client.send(push.get_message(target))
	except FCMError as error:
		log.status = "Failed"
		log.error = str(error)
		log.insert(ignore_permissions=True)
		raise
	log.status = "Sent"
	log.insert(ignore_permissions=True)
	return log.message_id
