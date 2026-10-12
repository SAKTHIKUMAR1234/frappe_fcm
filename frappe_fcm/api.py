import frappe

from frappe_fcm import devices


@frappe.whitelist(methods=["POST"])
def register_device(
	token: str, platform: str | None = None, app_name: str | None = None, app_version: str | None = None
) -> str:
	"""Get pushes on this device for the session user. Returns the device name."""
	return devices.register_device(frappe.session.user, token, platform, app_name, app_version)


@frappe.whitelist(methods=["POST"])
def remove_device(token: str):
	"""Stop pushes to the session user's device of `token`. A device of another user is refused."""
	owner = frappe.db.get_value(devices.DEVICE, {"token": token}, "user")
	if owner and owner != frappe.session.user:
		frappe.throw(frappe._("This device belongs to another user."), frappe.PermissionError)
	devices.remove_device(token)
