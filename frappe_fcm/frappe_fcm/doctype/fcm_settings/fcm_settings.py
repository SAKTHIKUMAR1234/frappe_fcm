# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

# The keys that FCM HTTP v1 needs from a Firebase service account key file.
REQUIRED_KEYS = ("type", "project_id", "private_key", "client_email", "token_uri")
WEB_FIELDS = ("api_key", "messaging_sender_id", "app_id", "vapid_key")


class FCMSettings(Document):
	def validate(self):
		self.project_id = None
		if self.service_account_file:
			self.project_id = parse_service_account(read_key_file(self.service_account_file))["project_id"]
		if self.enable_web_push:
			self.validate_web_config()

	def validate_web_config(self):
		labels = [self.meta.get_label(fieldname) for fieldname in WEB_FIELDS if not self.get(fieldname)]
		if not self.project_id:
			labels.append(_("Service Account Key File"))
		if labels:
			frappe.throw(_("Web push needs: {0}.").format(", ".join(labels)), frappe.MandatoryError)

	@property
	def service_account(self) -> dict | None:
		"""The service account key of the uploaded file, or None when no file is set."""
		return json.loads(read_key_file(self.service_account_file)) if self.service_account_file else None

	@property
	def web_config(self) -> dict | None:
		"""The Firebase web config of web push, or None when web push is off or not configured."""
		if not self.enable_web_push or not self.project_id or not all(self.get(key) for key in WEB_FIELDS):
			return None
		return {
			"apiKey": self.api_key,
			"authDomain": self.auth_domain,
			"projectId": self.project_id,
			"messagingSenderId": self.messaging_sender_id,
			"appId": self.app_id,
			"vapidKey": self.vapid_key,
		}


def read_key_file(file_url: str) -> str:
	"""The text of the key file. A public file is refused: the key is a secret."""
	file = frappe.get_doc("File", {"file_url": file_url})
	if not file.is_private:
		frappe.throw(_("Upload the service account key file as a private file."))
	return file.get_content()


def parse_service_account(value: str | bytes) -> dict:
	try:
		info = json.loads(value)
	except ValueError:
		frappe.throw(_("The service account key file is not valid JSON."))
	if not isinstance(info, dict) or info.get("type") != "service_account":
		frappe.throw(_("The file is not a Firebase service account key."))
	missing = [key for key in REQUIRED_KEYS if not info.get(key)]
	if missing:
		frappe.throw(_("The service account key file has no {0}.").format(", ".join(missing)))
	return info
