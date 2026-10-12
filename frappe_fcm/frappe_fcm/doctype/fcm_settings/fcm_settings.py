# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class FCMSettings(Document):
	def validate(self):
		value = self.service_account_json
		if value and not self.is_dummy_password(value):
			self.project_id = self.project_id or parse_service_account(value)["project_id"]

	@property
	def service_account(self) -> dict | None:
		"""The service account key, or None when not set."""
		value = self.get_password("service_account_json", raise_exception=False)
		return json.loads(value) if value else None


def parse_service_account(value: str) -> dict:
	try:
		info = json.loads(value)
	except ValueError:
		frappe.throw(_("Service Account JSON is not valid JSON."))
	if not isinstance(info, dict) or info.get("type") != "service_account" or not info.get("project_id"):
		frappe.throw(_("Service Account JSON must be a service account key with a project_id."))
	return info
