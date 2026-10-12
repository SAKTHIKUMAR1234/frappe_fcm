/* eslint-env serviceworker */
/* global firebase */
const REPORT_URL = "/api/method/frappe_fcm.api.report_event";

function reportEvent(messageId, event) {
	if (!messageId) return Promise.resolve();
	const query = new URLSearchParams({ message_id: messageId, event });
	// GET: a service worker has no CSRF token. The session cookie identifies the user.
	return fetch(`${REPORT_URL}?${query}`, { credentials: "same-origin" }).catch(() => {});
}

// Before importScripts: Firebase stops the click event of the notifications that it shows.
self.addEventListener("notificationclick", (event) => {
	const firebasePayload = event.notification.data?.FCM_MSG;
	const data = firebasePayload ? firebasePayload.data || {} : event.notification.data || {};
	const work = [reportEvent(data.fcm_message, "opened")];

	const link = firebasePayload?.fcmOptions?.link || firebasePayload?.notification?.click_action;
	if (!link) {
		event.notification.close();
		work.push(self.clients.openWindow(data.url || "/desk"));
	}
	event.waitUntil(Promise.all(work));
});

// The Firebase web config is the `config` query parameter of the registration.
const config = JSON.parse(new URL(self.location).searchParams.get("config") || "null");

if (config) {
	importScripts(
		"__FIREBASE_SDK_URL__/firebase-app-compat.js",
		"__FIREBASE_SDK_URL__/firebase-messaging-compat.js"
	);
	firebase.initializeApp(config);

	// Firebase shows a message with a `notification` block itself; a data-only message is shown here.
	firebase.messaging().onBackgroundMessage((payload) => {
		const data = payload.data || {};
		const work = [reportEvent(data.fcm_message, "delivered")];
		if (!payload.notification && data.title) {
			work.push(self.registration.showNotification(data.title, { body: data.body, data }));
		}
		return Promise.all(work);
	});
}
