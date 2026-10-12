import frappe

from frappe_fcm import api
from frappe_fcm.devices import DEVICE
from frappe_fcm.tests.fixtures import FCMTestCase


class TestAPI(FCMTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user(self.user)

	def test_register_is_for_the_session_user(self):
		token = frappe.generate_hash()

		name = api.register_device(token, "Web", "Shop", "2.0")

		self.assertEqual(frappe.db.get_value(DEVICE, name, ["user", "token"]), (self.user, token))

	def test_remove_deletes_an_own_device(self):
		device = self.add_device(self.user)

		api.remove_device(device.token)

		self.assertFalse(frappe.db.exists(DEVICE, device.name))

	def test_remove_refuses_a_device_of_another_user(self):
		device = self.add_device(self.other_user)

		with self.assertRaises(frappe.PermissionError):
			api.remove_device(device.token)

		self.assertTrue(frappe.db.exists(DEVICE, device.name))

	def test_endpoints_are_post_only_and_not_for_guests(self):
		for method in (api.register_device, api.remove_device):
			self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[method], ["POST"])
			self.assertNotIn(method, frappe.guest_methods)
