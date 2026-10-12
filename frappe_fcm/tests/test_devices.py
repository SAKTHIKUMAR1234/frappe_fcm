import frappe

from frappe_fcm.devices import DEVICE, disable_devices, get_enabled_devices, register_device, remove_device
from frappe_fcm.tests.fixtures import FCMTestCase


class TestDevices(FCMTestCase):
	def get_devices(self, token: str) -> list[dict]:
		return frappe.get_all(
			DEVICE, {"token": token}, ["user", "platform", "app_name", "app_version", "enabled"]
		)

	def test_register_creates_one_device_and_a_repeat_keeps_one_row(self):
		token = frappe.generate_hash()

		name = register_device(self.user, token, "Android", "Shop", "1.0")
		self.assertEqual(register_device(self.user, token, "Android", "Shop", "1.1"), name)

		self.assertEqual(
			self.get_devices(token),
			[
				{
					"user": self.user,
					"platform": "Android",
					"app_name": "Shop",
					"app_version": "1.1",
					"enabled": 1,
				}
			],
		)

	def test_a_token_moves_to_the_new_user_and_is_enabled_again(self):
		device = self.add_device(self.user, enabled=0)

		register_device(self.other_user, device.token, "iOS")

		(row,) = self.get_devices(device.token)
		self.assertEqual((row.user, row.platform, row.enabled), (self.other_user, "iOS", 1))

	def test_register_refuses_an_empty_token_and_an_unknown_platform(self):
		with self.assertRaisesRegex(frappe.ValidationError, "token is required"):
			register_device(self.user, "")
		with self.assertRaises(frappe.ValidationError):
			register_device(self.user, frappe.generate_hash(), "Windows")

	def test_remove_deletes_the_device(self):
		device = self.add_device(self.user)

		remove_device(device.token)
		remove_device("unknown")

		self.assertFalse(frappe.db.exists(DEVICE, device.name))

	def test_disable_stops_only_the_users_devices_of_the_app(self):
		shop = self.add_device(self.user, "Shop")
		other_app = self.add_device(self.user, "Other")
		other_user = self.add_device(self.other_user, "Shop")

		disable_devices(self.user, "Shop")

		enabled = [
			frappe.db.get_value(DEVICE, device.name, "enabled") for device in (shop, other_app, other_user)
		]
		self.assertEqual(enabled, [0, 1, 1])

	def test_enabled_devices_of_users_and_app(self):
		shop = self.add_device(self.user, "Shop")
		other_app = self.add_device(self.user, "Other")
		self.add_device(self.user, "Shop", enabled=0)
		self.add_device(frappe.session.user, "Shop")

		self.assertEqual([row.name for row in get_enabled_devices([self.user], "Shop")], [shop.name])
		self.assertCountEqual(
			[row.name for row in get_enabled_devices([self.user])], [shop.name, other_app.name]
		)
