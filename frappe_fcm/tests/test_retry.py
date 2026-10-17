from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now_datetime

from frappe_fcm import notifications, retry
from frappe_fcm.client import FCMError
from frappe_fcm.tests.test_notifications import NotificationTestCase


class TestNotificationRetry(NotificationTestCase):
	def setUp(self):
		super().setUp()
		self.device = self.add_device(self.user, "Shop")
		self.client = patch.object(retry, "get_client").start().return_value
		self.client.send.return_value = "projects/local/messages/1"

	def due(self, doc):
		frappe.db.set_value("FCM Notification", doc.name, "next_retry", None)

	def test_failure_retries_without_resending_successful_devices(self):
		self.add_device(self.user, "Shop")
		doc = self.add()
		self.client.send.side_effect = ["projects/local/messages/1", FCMError("UNAVAILABLE", "busy")]
		notifications.push_notification(doc.name)
		self.assertEqual(doc.reload().delivery_status, "Failed")
		self.client.send.side_effect = None
		self.due(doc)
		notifications.push_notification(doc.name)
		self.assertEqual(self.client.send.call_count, 3)
		self.assertEqual(doc.reload().delivery_status, "Sent")
		notifications.push_notification(doc.name)
		self.assertEqual(self.client.send.call_count, 3)

	def test_overlapping_worker_cannot_send_the_claimed_notification(self):
		doc = self.add()

		def send(message):
			self.assertEqual(doc.reload().delivery_status, "Processing")
			self.assertFalse(retry.claim(doc.name))
			return "projects/local/messages/1"

		self.client.send.side_effect = send
		notifications.push_notification(doc.name)
		self.client.send.assert_called_once()
		self.assertEqual(doc.reload().delivery_status, "Sent")

	def test_attempts_are_bounded_and_backoff_is_enforced(self):
		doc = self.add()
		self.client.send.side_effect = FCMError("UNAVAILABLE", "busy")
		for _ in range(retry.MAX_ATTEMPTS):
			self.due(doc)
			notifications.push_notification(doc.name)
			notifications.push_notification(doc.name)
		self.assertEqual(self.client.send.call_count, retry.MAX_ATTEMPTS)
		self.assertEqual(doc.reload().delivery_status, "Exhausted")

	def test_uncertain_send_and_crashed_claim_are_not_replayed(self):
		doc = self.add()
		self.client.send.side_effect = FCMError("DELIVERY_UNKNOWN", "timeout")
		notifications.push_notification(doc.name)
		self.assertEqual(doc.reload().delivery_status, "Unknown")
		self.due(doc)
		notifications.push_notification(doc.name)
		self.client.send.assert_called_once()
		other = self.add()
		self.assertTrue(retry.claim(other.name))
		notifications.push_notification(other.name)
		self.client.send.assert_called_once()

	def test_disabled_push_does_not_spend_attempts(self):
		doc = self.add()
		with patch.object(notifications, "get_push", return_value=None):
			notifications.push_notification(doc.name)
		self.assertEqual(doc.reload().attempts, 0)
		self.client.send.assert_not_called()

	def test_scheduler_only_queues_due_candidates(self):
		due = self.add()
		self.add(delivery_status="Sent")
		self.add(delivery_status="Failed", attempts=retry.MAX_ATTEMPTS)
		self.add(next_retry=add_to_date(now_datetime(), hours=1))
		with patch.object(frappe, "enqueue") as enqueue:
			retry.retry_notifications()
		names = [call.kwargs["name"] for call in enqueue.call_args_list]
		self.assertIn(due.name, names)
		self.assertLessEqual(len(names), retry.BATCH_SIZE)
