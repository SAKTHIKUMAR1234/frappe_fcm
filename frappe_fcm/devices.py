import hashlib

import frappe
from frappe import _
from frappe.utils import now_datetime

DEVICE = "FCM Device"
LOCK_WAIT_SECONDS = 10
# The length of the FCM Device `token` field.
TOKEN_LENGTH = 255
# A client's platform text, in lower case -> the FCM Device platform.
PLATFORMS = {"android": "Android", "ios": "iOS", "web": "Web"}


def register_device(
	user: str,
	token: str,
	platform: str | None = None,
	app_name: str | None = None,
	app_version: str | None = None,
) -> str:
	"""Make `token` an enabled device of `user` and return its name. One row per token: a token that
	another user held (one phone, another login) moves to `user`.

	The caller's transaction is committed first, and a named lock on the token is the first step of the
	new one. Two parallel registrations of one token would otherwise both insert, or update a row that
	the other committed after their first read (MariaDB error 1020)."""
	token = clean_token(token)
	if not token:
		frappe.throw(_("A valid FCM token is required."))
	frappe.db.commit()
	lock_token(token)

	name = frappe.db.get_value(DEVICE, {"token": token})
	doc = frappe.get_doc(DEVICE, name) if name else frappe.new_doc(DEVICE, token=token)
	doc.update(
		{
			"user": user,
			"platform": platform,
			"app_name": app_name,
			"app_version": app_version,
			"last_seen": now_datetime(),
			"enabled": 1,
		}
	)
	doc.save(ignore_permissions=True)
	return doc.name


def clean_token(token) -> str | None:
	"""The token without outer spaces; none when it is not text, empty or longer than `TOKEN_LENGTH`."""
	token = token.strip() if isinstance(token, str) else ""
	return token if 0 < len(token) <= TOKEN_LENGTH else None


def get_platform(value) -> str | None:
	"""The FCM Device platform of a client's text, such as `android`; unknown text gives none."""
	return PLATFORMS.get(value.strip().lower()) if isinstance(value, str) else None


def lock_token(token: str):
	"""MariaDB named lock on the token until the transaction ends."""
	lock = "fcm-device-" + hashlib.sha1(token.encode()).hexdigest()
	if frappe.db.sql("select get_lock(%s, %s)", (lock, LOCK_WAIT_SECONDS))[0][0] != 1:
		frappe.throw(_("The same device is being registered. Try again."))

	def release():
		frappe.db.sql("do release_lock(%s)", (lock,))

	frappe.db.after_commit.add(release)
	frappe.db.after_rollback.add(release)


def remove_device(token: str):
	"""Delete the device of `token`, if one exists."""
	frappe.db.delete(DEVICE, {"token": token})


def disable_devices(user: str, app_name: str | None = None):
	"""Stop pushes to every device of `user` (of `app_name` when given), for example at logout."""
	filters = {"user": user, "enabled": 1}
	if app_name:
		filters["app_name"] = app_name
	frappe.db.set_value(DEVICE, filters, "enabled", 0, update_modified=False)


def get_enabled_devices(users: list[str], app_name: str | None = None) -> list[frappe._dict]:
	"""`name`, `user` and `token` of the enabled devices of `users`."""
	filters = {"user": ("in", users), "enabled": 1}
	if app_name:
		filters["app_name"] = app_name
	return frappe.get_all(DEVICE, filters, ["name", "user", "token"])
