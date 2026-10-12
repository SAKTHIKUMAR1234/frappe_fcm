import json
from unittest.mock import patch

import frappe
import requests
from frappe.tests import IntegrationTestCase

from frappe_fcm.devices import DEVICE

SERVICE_ACCOUNT = {"type": "service_account", "project_id": "demo-project", "client_email": "push@demo"}
MESSAGE_ID = "projects/demo-project/messages/1"


def make_response(status: int, body: dict) -> requests.Response:
	response = requests.Response()
	response.status_code = status
	response._content = json.dumps(body).encode()
	return response


def make_error(status: int, code: str, error_code: str | None = None) -> requests.Response:
	details = [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": error_code}]
	return make_response(
		status, {"error": {"code": status, "status": code, "details": details if error_code else []}}
	)


class FCMTestCase(IntegrationTestCase):
	"""Two users with rollback after each test. `register_device` commits; the test keeps its rollback."""

	def setUp(self):
		patch.object(frappe.db, "commit").start()
		self.addCleanup(patch.stopall)
		self.addCleanup(frappe.db.rollback)
		self.user = self.make_user()
		self.other_user = self.make_user()

	def make_user(self) -> str:
		email = f"fcm-{frappe.generate_hash(length=8)}@example.com"
		return (
			frappe.get_doc({"doctype": "User", "email": email, "first_name": "FCM"})
			.insert(ignore_permissions=True)
			.name
		)

	def add_device(self, user: str, app_name: str | None = None, **values) -> frappe._dict:
		return frappe.get_doc(
			{"doctype": DEVICE, "user": user, "token": frappe.generate_hash(), "app_name": app_name, **values}
		).insert(ignore_permissions=True)

	def set_service_account(self):
		settings = frappe.get_single("FCM Settings")
		settings.service_account_json = json.dumps(SERVICE_ACCOUNT)
		settings.save(ignore_permissions=True)

	def mock_http(self, *responses: requests.Response):
		"""FCM HTTP answers `responses` in order; returns the mocked `post`."""
		patch(
			"frappe_fcm.client.service_account.Credentials.from_service_account_info", return_value=object()
		).start()
		patch("frappe_fcm.client.AuthorizedSession.__init__", return_value=None).start()
		return patch("frappe_fcm.client.AuthorizedSession.post", side_effect=list(responses)).start()
