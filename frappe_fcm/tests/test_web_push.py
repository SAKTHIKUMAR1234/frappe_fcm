import frappe
from frappe.website.serve import get_response

from frappe_fcm import web_push
from frappe_fcm.tests.fixtures import FCMTestCase

WEB_CONFIG = {
	"api_key": "key",
	"auth_domain": "demo-project.firebaseapp.com",
	"messaging_sender_id": "123",
	"app_id": "1:123:web:abc",
	"vapid_key": "vapid",
}


class TestWebPush(FCMTestCase):
	def setUp(self):
		super().setUp()
		self.set_service_account()
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user(self.user)

	def set_web_push(self, enabled: int, **values):
		settings = frappe.get_single("FCM Settings")
		settings.update({**{key: None for key in WEB_CONFIG}, **values, "enable_web_push": enabled})
		settings.save(ignore_permissions=True)

	def get_boot(self) -> frappe._dict:
		bootinfo = frappe._dict()
		web_push.boot(bootinfo)
		return bootinfo

	def test_enabled_and_configured_gives_the_config(self):
		self.set_web_push(1, **WEB_CONFIG)

		settings = self.get_boot().fcm_web_push

		self.assertEqual(settings["sdk_url"], web_push.FIREBASE_SDK_URL)
		self.assertEqual(
			settings["config"],
			{
				"apiKey": "key",
				"authDomain": "demo-project.firebaseapp.com",
				"projectId": "demo-project",
				"messagingSenderId": "123",
				"appId": "1:123:web:abc",
				"vapidKey": "vapid",
			},
		)

	def test_disabled_web_push_gives_nothing(self):
		self.set_web_push(0, **WEB_CONFIG)

		self.assertNotIn("fcm_web_push", self.get_boot())

	def test_web_push_without_a_project_gives_nothing(self):
		self.set_web_push(1, **WEB_CONFIG)
		frappe.db.set_single_value("FCM Settings", "project_id", None)
		frappe.clear_document_cache("FCM Settings", "FCM Settings")

		self.assertNotIn("fcm_web_push", self.get_boot())

	def test_enabled_needs_the_web_config(self):
		with self.assertRaises(frappe.MandatoryError):
			self.set_web_push(1, api_key="key")

	def test_guests_get_nothing(self):
		self.set_web_push(1, **WEB_CONFIG)
		frappe.set_user("Guest")

		self.assertNotIn("fcm_web_push", self.get_boot())

	def test_the_service_worker_is_served_at_the_site_root(self):
		frappe.set_user("Guest")

		response = get_response(web_push.SERVICE_WORKER_PATH)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.mimetype, "text/javascript")
		script = response.get_data(as_text=True)
		self.assertIn(f"{web_push.FIREBASE_SDK_URL}/firebase-messaging-compat.js", script)
		self.assertIn("frappe_fcm.api.report_event", script)
