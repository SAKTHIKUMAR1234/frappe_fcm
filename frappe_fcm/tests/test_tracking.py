import frappe
from frappe.utils import now_datetime

from frappe_fcm import api
from frappe_fcm.push import MESSAGE_LOG
from frappe_fcm.tests.fixtures import MESSAGE_ID, FCMTestCase


class TestTracking(FCMTestCase):
	def setUp(self):
		super().setUp()
		self.set_service_account()
		self.addCleanup(frappe.set_user, frappe.session.user)
		self.addCleanup(setattr, frappe.flags, "commit", False)
		frappe.set_user(self.user)

	def add_log(self, user: str | None = None, status: str = "Sent", message_id: str = MESSAGE_ID):
		return frappe.get_doc(
			{"doctype": MESSAGE_LOG, "target": "t", "user": user, "status": status, "message_id": message_id}
		).insert(ignore_permissions=True)

	def get_times(self, name: str) -> tuple:
		return frappe.db.get_value(MESSAGE_LOG, name, ["delivered_on", "opened_on"])

	def test_delivered_then_opened_keeps_the_first_times(self):
		log = self.add_log(self.user)

		api.report_event(log.name, "delivered")
		delivered_on, opened_on = self.get_times(log.name)
		self.assertIsNotNone(delivered_on)
		self.assertIsNone(opened_on)

		api.report_event(log.name, "opened")
		api.report_event(log.name, "delivered")
		self.assertEqual(self.get_times(log.name)[0], delivered_on)
		self.assertIsNotNone(self.get_times(log.name)[1])

	def test_opened_also_marks_delivered(self):
		log = self.add_log(self.user)

		api.report_event(log.name, "opened")

		self.assertTrue(all(self.get_times(log.name)))
		self.assertTrue(frappe.flags.commit, "a GET request must commit")

	def test_the_fcm_message_id_in_full_or_short_finds_the_log(self):
		full = self.add_log(self.user, message_id="projects/demo-project/messages/0:11%aa")
		short = self.add_log(self.user, message_id="projects/demo-project/messages/0:22%bb")

		api.report_event(full.message_id, "opened")
		api.report_event("0:22%bb", "opened")

		self.assertTrue(all(self.get_times(full.name)))
		self.assertTrue(all(self.get_times(short.name)))

	def test_a_message_of_another_user_or_a_topic_is_refused(self):
		for log in (self.add_log(self.other_user), self.add_log(None)):
			with self.assertRaises(frappe.PermissionError):
				api.report_event(log.name, "opened")
			self.assertEqual(self.get_times(log.name), (None, None))

	def test_an_unknown_message_event_or_failed_send_is_refused(self):
		failed = self.add_log(self.user, status="Failed", message_id=None)
		for message_id in ("missing", ""):
			with self.assertRaises(frappe.DoesNotExistError):
				api.report_event(message_id, "opened")
		with self.assertRaises(frappe.ValidationError):
			api.report_event(self.add_log(self.user).name, "read")
		with self.assertRaises(frappe.ValidationError):
			api.report_event(failed.name, "delivered")

	def test_counts_of_sent_delivered_opened_and_failed(self):
		frappe.db.delete(MESSAGE_LOG)
		logs = [self.add_log(self.user) for _ in range(4)]
		self.add_log(self.user, status="Failed", message_id=None)
		other = self.add_log(self.other_user)
		frappe.db.set_value(MESSAGE_LOG, logs[0].name, "delivered_on", now_datetime())
		frappe.db.set_value(
			MESSAGE_LOG, logs[1].name, {"delivered_on": now_datetime(), "opened_on": now_datetime()}
		)
		frappe.db.set_value(MESSAGE_LOG, other.name, "opened_on", now_datetime())
		frappe.set_user("Administrator")

		self.assertEqual(
			api.get_message_counts(),
			{"sent": 5, "delivered": 2, "opened": 2, "failed": 1},
		)
		self.assertEqual(
			api.get_message_counts(frappe.as_json([[MESSAGE_LOG, "user", "=", self.user]])),
			{"sent": 4, "delivered": 2, "opened": 1, "failed": 1},
		)

	def test_counts_need_read_access_to_the_log(self):
		with self.assertRaises(frappe.PermissionError):
			api.get_message_counts()

	def test_report_allows_get_for_the_service_worker_and_not_guests(self):
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[api.report_event], ["GET", "POST"])
		self.assertNotIn(api.report_event, frappe.guest_methods)
