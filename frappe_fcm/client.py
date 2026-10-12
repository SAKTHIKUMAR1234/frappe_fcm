import frappe
import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{}/messages:send"
TIMEOUT_SECONDS = 10


class FCMError(Exception):
	"""A send that FCM refused or that did not reach FCM. `code` is the FCM error code, such as
	`UNREGISTERED`."""

	def __init__(self, code: str, message: str):
		super().__init__(f"{code}: {message}")
		self.code = code


class FCMClient:
	"""FCM HTTP v1 with a service account (OAuth 2 access tokens from google-auth)."""

	def __init__(self, service_account_info: dict, project_id: str):
		credentials = service_account.Credentials.from_service_account_info(
			service_account_info, scopes=[SCOPE]
		)
		self.session = AuthorizedSession(credentials)
		self.url = SEND_URL.format(project_id)

	def send(self, message: dict) -> str:
		"""Send one message and return its id, such as `projects/<project>/messages/<id>`."""
		try:
			response = self.session.post(self.url, json={"message": message}, timeout=TIMEOUT_SECONDS)
		except requests.RequestException as error:
			raise FCMError("UNAVAILABLE", str(error))
		if not response.ok:
			raise FCMError(get_error_code(response), response.text[:1000])
		return response.json()["name"]


def get_error_code(response: requests.Response) -> str:
	"""The FCM error code of a failed send; the HTTP status when the body has none."""
	try:
		error = response.json()["error"]
	except ValueError, KeyError, TypeError:
		return str(response.status_code)
	for detail in error.get("details") or []:
		if detail.get("errorCode"):
			return detail["errorCode"]
	return error.get("status") or str(response.status_code)


def get_client() -> FCMClient | None:
	"""The client of FCM Settings; None, with a log line, when no service account is set."""
	settings = frappe.get_single("FCM Settings")
	info = settings.service_account
	if not info:
		frappe.logger("frappe_fcm").warning("FCM Settings has no service account; push not sent.")
		return None
	return FCMClient(info, settings.project_id or info["project_id"])
