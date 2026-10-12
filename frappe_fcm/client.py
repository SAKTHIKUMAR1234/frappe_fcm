import frappe
import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL = "https://fcm.googleapis.com/v1/projects/{}/messages:send"
TIMEOUT_SECONDS = 10


# Error codes of a token that no longer reaches a device.
DEAD_TOKEN_CODES = {"UNREGISTERED", "NOT_FOUND"}
# The field that an INVALID_ARGUMENT names when the registration token itself is invalid.
TOKEN_FIELD = "message.token"


class FCMError(Exception):
	"""A send that FCM refused or that did not reach FCM. `code` is the FCM error code, such as
	`UNREGISTERED`. `is_dead_token` is set when FCM says the token itself no longer works."""

	def __init__(self, code: str, message: str, is_dead_token: bool = False):
		super().__init__(f"{code}: {message}")
		self.code = code
		self.is_dead_token = is_dead_token


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
			raise get_error(response)
		return response.json()["name"]


def get_error(response: requests.Response) -> FCMError:
	"""The error of a failed send. The token is dead on UNREGISTERED or NOT_FOUND, or on an
	INVALID_ARGUMENT whose `fieldViolations` name `message.token`."""
	try:
		error = response.json()["error"]
	except ValueError, KeyError, TypeError:
		return FCMError(str(response.status_code), response.text[:1000])

	details = error.get("details") or []
	codes = {error.get("status"), *(detail.get("errorCode") for detail in details)}
	error_code = next((detail["errorCode"] for detail in details if detail.get("errorCode")), None)
	fields = {
		violation.get("field") for detail in details for violation in detail.get("fieldViolations") or []
	}
	is_dead_token = bool(codes & DEAD_TOKEN_CODES) or ("INVALID_ARGUMENT" in codes and TOKEN_FIELD in fields)
	code = error_code or error.get("status") or str(response.status_code)
	return FCMError(code, error.get("message") or response.text[:1000], is_dead_token)


def get_client() -> FCMClient | None:
	"""The client of FCM Settings; None, with a log line, when no service account is set."""
	settings = frappe.get_single("FCM Settings")
	info = settings.service_account
	if not info:
		frappe.logger("frappe_fcm").warning("FCM Settings has no service account; push not sent.")
		return None
	return FCMClient(info, settings.project_id or info["project_id"])
