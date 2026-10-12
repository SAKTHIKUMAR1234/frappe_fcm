import json
from unittest.mock import patch

import frappe
import requests
from frappe.utils import add_days, now_datetime

from frappe_fcm import push
from frappe_fcm.devices import DEVICE
from frappe_fcm.frappe_fcm.doctype.fcm_message_log.fcm_message_log import FCMMessageLog
from frappe_fcm.push import MESSAGE_LOG, Push, deliver_to_topic, deliver_to_users
from frappe_fcm.tests.fixtures import MESSAGE_ID, FCMTestCase, make_error, make_response


class TestSend(FCMTestCase):
	def test_send_to_users_queues_on_the_short_queue_after_commit(self):
		with patch.object(frappe, "enqueue") as enqueue:
			push.send_to_users(
				{self.user}, "Hi", "Body", {"a": "1"}, "Shop", data_only=True, collapse_key="k"
			)

		enqueue.assert_called_once_with(
			"frappe_fcm.push.deliver_to_users",
			queue="short",
			enqueue_after_commit=True,
			users=[self.user],
			push=Push("Hi", "Body", {"a": "1"}, True, "k"),
			app_name="Shop",
		)

	def test_send_to_topic_queues_on_the_short_queue_after_commit(self):
		with patch.object(frappe, "enqueue") as enqueue:
			push.send_to_topic("news", "Hi", "Body")

		enqueue.assert_called_once_with(
			"frappe_fcm.push.deliver_to_topic",
			queue="short",
			enqueue_after_commit=True,
			topic="news",
			push=Push("Hi", "Body"),
		)


class TestMessage(FCMTestCase):
	def test_a_notification_message_with_text_data(self):
		message = Push("Hi", "Body", {"count": 2, "name": "A"}).get_message({"token": "t"})

		self.assertEqual(
			message,
			{
				"token": "t",
				"data": {"count": "2", "name": "A"},
				"notification": {"title": "Hi", "body": "Body"},
			},
		)

	def test_a_data_only_message_carries_title_body_and_collapse_key(self):
		message = Push("Hi", "Body", {"body": "own"}, data_only=True, collapse_key="k").get_message(
			{"topic": "news"}
		)

		self.assertEqual(
			message,
			{"topic": "news", "data": {"title": "Hi", "body": "own"}, "android": {"collapse_key": "k"}},
		)


class TestDeliver(FCMTestCase):
	def setUp(self):
		super().setUp()
		self.set_service_account()
		self.device = self.add_device(self.user, "Shop")

	def get_log(self, target: str) -> dict:
		(log,) = frappe.get_all(
			MESSAGE_LOG, {"target": target}, ["user", "status", "message_id", "title", "data", "error"]
		)
		return log

	def test_success_returns_the_message_id_and_writes_the_log(self):
		post = self.mock_http(make_response(200, {"name": MESSAGE_ID}))

		message_ids = deliver_to_users([self.user], Push("Hi", "Body", {"a": "1"}), "Shop")

		self.assertEqual(message_ids, [MESSAGE_ID])
		self.assertEqual(
			post.call_args.args[0], "https://fcm.googleapis.com/v1/projects/demo-project/messages:send"
		)
		self.assertEqual(post.call_args.kwargs["json"]["message"]["token"], self.device.token)
		log = self.get_log(self.device.token)
		self.assertEqual(
			(log.user, log.status, log.message_id, log.title, json.loads(log.data)),
			(self.user, "Sent", MESSAGE_ID, "Hi", {"a": "1"}),
		)

	def test_a_dead_token_deletes_the_device_and_logs_the_error(self):
		dead = {
			"UNREGISTERED": make_error(404, "NOT_FOUND", "UNREGISTERED"),
			"NOT_FOUND": make_error(404, "NOT_FOUND"),
			"INVALID_ARGUMENT": make_error(400, "INVALID_ARGUMENT", "INVALID_ARGUMENT", "message.token"),
		}
		for code, response in dead.items():
			device = self.add_device(self.other_user)
			self.mock_http(response)

			self.assertEqual(deliver_to_users([self.other_user], Push("Hi", "Body")), [])

			self.assertFalse(frappe.db.exists(DEVICE, device.name), code)
			log = self.get_log(device.token)
			self.assertEqual(log.status, "Failed")
			self.assertTrue(log.error.startswith(code))

	def test_an_invalid_argument_of_the_message_keeps_the_device(self):
		for response in (
			make_error(400, "INVALID_ARGUMENT", "INVALID_ARGUMENT", "message.data[0].value"),
			make_error(400, "INVALID_ARGUMENT", "INVALID_ARGUMENT"),
		):
			self.mock_http(response)

			self.assertEqual(deliver_to_users([self.user], Push("Hi", "Body"), "Shop"), [])

			self.assertTrue(frappe.db.exists(DEVICE, self.device.name))
		logs = frappe.get_all(MESSAGE_LOG, {"target": self.device.token}, pluck="status")
		self.assertEqual(logs, ["Failed", "Failed"])

	def test_another_error_keeps_the_device(self):
		self.mock_http(make_error(503, "UNAVAILABLE"), requests.ConnectionError("down"))
		second = self.add_device(self.user, "Shop")

		self.assertEqual(deliver_to_users([self.user], Push("Hi", "Body"), "Shop"), [])

		self.assertTrue(frappe.db.exists(DEVICE, self.device.name))
		self.assertTrue(frappe.db.exists(DEVICE, second.name))
		self.assertEqual(self.get_log(second.token).status, "Failed")

	def test_no_send_to_a_disabled_device_or_another_app(self):
		post = self.mock_http()
		frappe.db.set_value(DEVICE, self.device.name, "enabled", 0)
		self.add_device(self.user, "Other")

		self.assertEqual(deliver_to_users([self.user], Push("Hi", "Body"), "Shop"), [])

		post.assert_not_called()

	def test_no_send_without_a_service_account(self):
		frappe.db.delete("__Auth", {"doctype": "FCM Settings"})
		post = self.mock_http()

		self.assertEqual(deliver_to_users([self.user], Push("Hi", "Body")), [])

		post.assert_not_called()

	def test_topic_success_and_failure(self):
		self.mock_http(make_response(200, {"name": MESSAGE_ID}), make_error(400, "INVALID_ARGUMENT"))

		self.assertEqual(deliver_to_topic("news", Push("Hi", "Body")), MESSAGE_ID)
		self.assertIsNone(deliver_to_topic("sale", Push("Hi", "Body")))

		self.assertEqual(self.get_log("news").status, "Sent")
		self.assertEqual(self.get_log("sale").status, "Failed")


class TestSettingsAndLog(FCMTestCase):
	def test_project_id_comes_from_the_service_account(self):
		self.set_service_account()

		settings = frappe.get_single("FCM Settings")

		self.assertEqual(settings.project_id, "demo-project")
		self.assertEqual(settings.service_account["client_email"], "push@demo")

	def test_a_value_that_is_not_a_service_account_is_refused(self):
		settings = frappe.get_single("FCM Settings")
		for value in ("not json", json.dumps({"type": "authorized_user"})):
			settings.service_account_json = value
			with self.assertRaises(frappe.ValidationError):
				settings.save(ignore_permissions=True)

	def test_old_logs_are_cleared(self):
		old = frappe.get_doc({"doctype": MESSAGE_LOG, "target": "t", "status": "Sent"}).insert()
		new = frappe.get_doc({"doctype": MESSAGE_LOG, "target": "t", "status": "Sent"}).insert()
		frappe.db.set_value(MESSAGE_LOG, old.name, "creation", add_days(now_datetime(), -31))

		FCMMessageLog.clear_old_logs(days=30)

		self.assertEqual(
			[frappe.db.exists(MESSAGE_LOG, name) for name in (old.name, new.name)], [None, new.name]
		)
