import json
from unittest.mock import ANY, call, patch

import frappe
from frappe.utils import CallbackManager

from frappe_fcm import api, notifications
from frappe_fcm.notifications import NOTIFICATION, notify
from frappe_fcm.push import MESSAGE_LOG, Push
from frappe_fcm.tests.fixtures import MESSAGE_ID, FCMTestCase, make_error, make_response

HOOK = "frappe_fcm.tests.test_notifications.get_shop_push"
REALTIME_HOOK = "frappe_fcm.tests.test_notifications.get_shop_realtime"


def get_shop_push(doc) -> Push | None:
	"""An app's `fcm_push` hook: a data-only push, none for a title `skip`."""
	return None if doc.title == "skip" else Push(doc.title, doc.body, {"id": doc.name}, data_only=True)


def get_shop_realtime(doc) -> tuple[str, dict] | None:
	"""An app's `fcm_realtime` hook: its own event, none for a title `skip`."""
	return (
		None
		if doc.title == "skip"
		else ("shop_notification", {"id": doc.name, "operation": doc.app_operation})
	)


class NotificationTestCase(FCMTestCase):
	def add(self, user: str | None = None, app_name: str | None = "Shop", **values):
		doc = frappe.get_doc(
			{
				"doctype": NOTIFICATION,
				"user": user or self.user,
				"app_name": app_name,
				"title": "Hi",
				"body": "Body",
				**values,
			}
		)
		doc.flags.skip_push = True
		return doc.insert(ignore_permissions=True)

	def is_read(self, name: str) -> int:
		return frappe.db.get_value(NOTIFICATION, name, "read")


class TestNotify(NotificationTestCase):
	def test_notify_inserts_and_queues_a_push_after_commit(self):
		with patch.object(frappe, "enqueue") as enqueue:
			doc = notify(self.user, "Hi", "Body", {"a": 1}, "Shop", reference_doctype="User")
			self.add()

		self.assertEqual(
			(doc.user, json.loads(doc.data), doc.reference_doctype), (self.user, {"a": 1}, "User")
		)
		enqueue.assert_called_once_with(
			"frappe_fcm.notifications.push_notification",
			queue="short",
			enqueue_after_commit=True,
			name=doc.name,
		)


class TestPushNotification(NotificationTestCase):
	def setUp(self):
		super().setUp()
		self.set_service_account()
		self.device = self.add_device(self.user, "Shop")
		get_hooks = frappe.get_hooks

		def get_test_hooks(hook=None, default=None, *args, **kwargs):
			if hook == "fcm_push":
				return {"Shop": [HOOK]}
			return get_hooks(hook, default, *args, **kwargs)

		self.get_hooks = patch.object(frappe, "get_hooks", side_effect=get_test_hooks)

	def test_deleted_notification_skips_without_sending_or_logging(self):
		post = self.mock_http()
		doc = self.add()
		frappe.delete_doc(NOTIFICATION, doc.name, ignore_permissions=True)
		error_count = frappe.db.count("Error Log")
		with patch.object(frappe, "log_error") as log_error:
			self.assertIsNone(notifications.push_notification(doc.name))
		post.assert_not_called()
		log_error.assert_not_called()
		self.assertEqual(frappe.db.count("Error Log"), error_count)
		self.assertFalse(frappe.db.exists(MESSAGE_LOG, {"target": self.device.token}))

	def test_real_send_failure_is_still_logged(self):
		post = self.mock_http(make_error(503, "UNAVAILABLE"))
		doc = self.add()
		notifications.push_notification(doc.name)
		post.assert_called_once()
		log = frappe.get_doc(MESSAGE_LOG, {"target": self.device.token})
		self.assertEqual(log.status, "Failed")
		self.assertIn("UNAVAILABLE", log.error)
		self.assertIsNone(frappe.db.get_value(NOTIFICATION, doc.name, "message_id"))

	def test_missing_record_in_push_builder_is_not_swallowed(self):
		doc = self.add()
		with patch.object(notifications, "get_push", side_effect=frappe.DoesNotExistError):
			with self.assertRaises(frappe.DoesNotExistError):
				notifications.push_notification(doc.name)

	def test_the_default_push_carries_the_name_and_keeps_the_message_id(self):
		post = self.mock_http(make_response(200, {"name": MESSAGE_ID}))
		doc = self.add(data=json.dumps({"a": "1"}))

		notifications.push_notification(doc.name)

		message = post.call_args.kwargs["json"]["message"]
		self.assertEqual(message["data"], {"a": "1", "notification": doc.name, "fcm_message": ANY})
		self.assertEqual(message["notification"], {"title": "Hi", "body": "Body"})
		self.assertEqual(frappe.db.get_value(NOTIFICATION, doc.name, "message_id"), MESSAGE_ID)

	def test_the_app_hook_builds_the_push(self):
		post = self.mock_http(make_response(200, {"name": MESSAGE_ID}))
		doc = self.add()

		with self.get_hooks:
			notifications.push_notification(doc.name)

		message = post.call_args.kwargs["json"]["message"]
		self.assertEqual(message["data"], {"title": "Hi", "body": "Body", "id": doc.name, "fcm_message": ANY})
		self.assertNotIn("notification", message)

	def test_the_app_hook_can_skip_the_push(self):
		post = self.mock_http()
		doc = self.add(title="skip")

		with self.get_hooks:
			notifications.push_notification(doc.name)

		post.assert_not_called()
		self.assertIsNone(frappe.db.get_value(NOTIFICATION, doc.name, "message_id"))


class TestRealtime(NotificationTestCase):
	def setUp(self):
		super().setUp()
		patch.object(frappe, "enqueue").start()
		patch.object(frappe.db, "after_commit", CallbackManager()).start()
		self.publish = patch.object(frappe, "publish_realtime").start()
		get_hooks = frappe.get_hooks

		def get_test_hooks(hook=None, default=None, *args, **kwargs):
			if hook == "fcm_realtime":
				return {"Shop": [REALTIME_HOOK]}
			return get_hooks(hook, default, *args, **kwargs)

		patch.object(frappe, "get_hooks", side_effect=get_test_hooks).start()

	def get_events(self) -> list:
		"""The published user events; the desk's own `doc_update` and `list_update` events are left out."""
		return [call for call in self.publish.call_args_list if "user" in call.kwargs]

	def test_the_default_event_carries_only_the_name_to_the_user_after_commit(self):
		doc = notify(self.user, "Hi", "Body", {"secret": "x"}, "Other")
		self.assertEqual(self.get_events(), [])

		frappe.db.after_commit.run()

		self.assertEqual(
			self.get_events(), [call("fcm_notification", {"notification": doc.name}, user=self.user)]
		)

	def test_the_app_hook_builds_the_event(self):
		doc = notify(self.user, "Hi", "Body", app_name="Shop", app_operation="order")

		frappe.db.after_commit.run()

		self.assertEqual(
			self.get_events(),
			[call("shop_notification", {"id": doc.name, "operation": "order"}, user=self.user)],
		)

	def test_the_app_hook_can_skip_and_a_migrated_row_sends_nothing(self):
		notify(self.user, "skip", "Body", app_name="Shop")
		self.add()

		frappe.db.after_commit.run()

		self.assertEqual(self.get_events(), [])

	def test_a_rolled_back_notification_sends_nothing(self):
		notify(self.user, "Hi", "Body", app_name="Shop")

		frappe.db.rollback()
		frappe.db.after_commit.run()

		self.assertEqual(self.get_events(), [])


class TestInbox(NotificationTestCase):
	def test_list_has_only_the_users_rows_of_the_app_newest_first(self):
		first = self.add().name
		second = self.add(reference_doctype="User", reference_name=self.user).name
		self.add(app_name="Other")
		self.add(self.other_user)

		rows = notifications.get_notifications(self.user, "Shop")
		page = notifications.get_notifications(self.user, "Shop", start=1, page_length=1)

		self.assertEqual([row.name for row in rows], [second, first])
		self.assertEqual(rows[0].reference_name, self.user)
		self.assertIn("app_operation", rows[0])
		self.assertEqual([row.name for row in page], [first])
		self.assertEqual(notifications.count_notifications(self.user, "Shop"), 2)
		self.assertEqual(notifications.count_notifications(self.user), 3)

	def test_mark_read_one_and_all_own_rows_only(self):
		own = [self.add().name for _index in range(2)]
		other_app = self.add(app_name="Other").name
		other_user = self.add(self.other_user).name

		notifications.mark_read(self.user, own[0], "Shop")
		self.assertEqual([self.is_read(name) for name in own], [1, 0])

		notifications.mark_read(self.user, app_name="Shop")
		self.assertEqual([self.is_read(name) for name in (*own, other_app, other_user)], [1, 1, 0, 0])

	def test_mark_read_refuses_another_users_or_apps_row(self):
		for name in (self.add(self.other_user).name, self.add(app_name="Other").name):
			with self.assertRaises(frappe.DoesNotExistError):
				notifications.mark_read(self.user, name, "Shop")
			self.assertEqual(self.is_read(name), 0)

	def test_find_by_message_id_or_name(self):
		pushed = self.add(message_id=MESSAGE_ID).name
		unpushed = self.add().name
		foreign = self.add(self.other_user).name

		self.assertEqual(notifications.find_by_message_id(self.user, MESSAGE_ID, "Shop"), pushed)
		self.assertEqual(notifications.find_by_message_id(self.user, unpushed, "Shop"), unpushed)
		self.assertIsNone(notifications.find_by_message_id(self.user, foreign, "Shop"))


class TestInboxAPI(NotificationTestCase):
	def setUp(self):
		super().setUp()
		self.own = self.add().name
		self.foreign = self.add(self.other_user).name
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user(self.user)

	def test_list_and_rest_rows_are_the_session_users(self):
		self.assertEqual([row.name for row in api.get_notifications("Shop")], [self.own])
		self.assertEqual(frappe.get_list(NOTIFICATION, pluck="name"), [self.own])
		self.assertTrue(frappe.has_permission(NOTIFICATION, doc=self.own))
		self.assertFalse(frappe.has_permission(NOTIFICATION, doc=self.foreign))

	def test_mark_read_refuses_a_foreign_row(self):
		api.mark_read(self.own)
		with self.assertRaises(frappe.DoesNotExistError):
			api.mark_read(self.foreign)

		self.assertEqual([self.is_read(name) for name in (self.own, self.foreign)], [1, 0])
