import frappe
from frappe.tests.test_api import FrappeAPITestCase

from frappe_fcm.devices import DEVICE
from frappe_fcm.notifications import NOTIFICATION

API = "/api/method/frappe_fcm.api"


class TestAPIHTTP(FrappeAPITestCase):
	"""The inbox and device endpoints over HTTP with committed rows of two API key users."""

	def setUp(self):
		self.users = [self.make_user(), self.make_user()]
		frappe.db.commit()
		self.addCleanup(self.delete_rows)

	def make_user(self) -> frappe._dict:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"fcm-http-{frappe.generate_hash(length=8)}@example.com",
				"first_name": "FCM",
			}
		)
		user.api_key = frappe.generate_hash(length=15)
		user.insert(ignore_permissions=True)
		secret = frappe.generate_hash(length=15)
		user.api_secret = secret
		user.save(ignore_permissions=True)
		return frappe._dict(name=user.name, auth=f"token {user.api_key}:{secret}")

	def delete_rows(self):
		names = [user.name for user in self.users]
		for doctype in (NOTIFICATION, DEVICE):
			frappe.db.delete(doctype, {"user": ("in", names)})
		for name in names:
			frappe.delete_doc("User", name, force=True, ignore_permissions=True)
		frappe.db.commit()

	def add_notification(self, user: str) -> str:
		doc = frappe.get_doc(
			{
				"doctype": NOTIFICATION,
				"user": user,
				"app_name": "Shop",
				"title": "Hi",
				"app_operation": "open",
			}
		)
		doc.flags.skip_push = True
		name = doc.insert(ignore_permissions=True).name
		frappe.db.commit()
		return name

	def call(self, method: str, user: frappe._dict | None = None, http_method: str = "GET", **params):
		headers = {"Authorization": user.auth} if user else {}
		if http_method == "GET":
			return self.get(f"{API}.{method}", params, headers=headers)
		return self.post(f"{API}.{method}", params, headers=headers)

	def test_list_and_mark_read_are_the_callers_rows_only(self):
		own = self.add_notification(self.users[0].name)
		foreign = self.add_notification(self.users[1].name)

		listed = self.call("get_notifications", self.users[0], app_name="Shop")
		marked = self.call("mark_read", self.users[0], "POST", name=own)
		refused = self.call("mark_read", self.users[0], "POST", name=foreign)

		self.assertEqual((listed.status_code, marked.status_code, refused.status_code), (200, 200, 404))
		(row,) = listed.json["message"]
		self.assertEqual((row["name"], row["app_operation"], row["read"]), (own, "open", 0))
		frappe.db.rollback()
		self.assertEqual([frappe.db.get_value(NOTIFICATION, name, "read") for name in (own, foreign)], [1, 0])

	def test_register_and_remove_a_device(self):
		token = frappe.generate_hash()

		registered = self.call(
			"register_device", self.users[0], "POST", token=f" {token} ", platform="Android"
		)
		foreign = self.call("remove_device", self.users[1], "POST", token=token)
		removed = self.call("remove_device", self.users[0], "POST", token=token)

		self.assertEqual(registered.status_code, 200)
		self.assertIsInstance(registered.json["message"], str)
		self.assertEqual((foreign.status_code, removed.status_code), (403, 200))
		frappe.db.rollback()
		self.assertFalse(frappe.db.exists(DEVICE, {"token": token}))

	def test_refusals(self):
		guest = self.call("get_notifications")
		get_register = self.call("register_device", self.users[0], token=frappe.generate_hash())
		empty_token = self.call("register_device", self.users[0], "POST", token="  ")

		self.assertIn(guest.status_code, (401, 403))
		self.assertEqual((get_register.status_code, empty_token.status_code), (403, 417))
