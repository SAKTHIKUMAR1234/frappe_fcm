/* global firebase */
// Registers the browser of the desk user for web push. `frappe.boot.fcm_web_push` is set only when web
// push is on and configured; without it nothing is loaded.
{
	const web_push = {
		APP_NAME: "Desk",

		start() {
			const settings = frappe.boot.fcm_web_push;
			if (!settings || !("serviceWorker" in navigator) || !("Notification" in window))
				return;

			if (Notification.permission === "granted") {
				this.register(settings);
			} else if (Notification.permission === "default") {
				// Browsers ask for the permission only after a user gesture.
				const ask = () =>
					Notification.requestPermission().then(
						(permission) => permission === "granted" && this.register(settings)
					);
				document.addEventListener("click", ask, { once: true });
			}
		},

		async register({ config, sdk_url }) {
			const { vapidKey, ...firebaseConfig } = config;
			await this.load_script(`${sdk_url}/firebase-app-compat.js`);
			await this.load_script(`${sdk_url}/firebase-messaging-compat.js`);

			const query = new URLSearchParams({ config: JSON.stringify(firebaseConfig) });
			// The Firebase default scope keeps the site root free for another service worker.
			const registration = await navigator.serviceWorker.register(
				`/firebase-messaging-sw.js?${query}`,
				{ scope: "/firebase-cloud-messaging-push-scope" }
			);
			const messaging = firebase.initializeApp(firebaseConfig).messaging();
			const token = await messaging.getToken({
				vapidKey,
				serviceWorkerRegistration: registration,
			});
			await frappe.xcall("frappe_fcm.api.register_device", {
				token,
				platform: "Web",
				app_name: this.APP_NAME,
			});

			// A message that arrives while the desk is open is shown as an alert.
			messaging.onMessage((payload) => {
				const data = payload.data || {};
				const title = payload.notification?.title || data.title;
				if (title) frappe.show_alert({ message: title, indicator: "blue" });
				if (data.fcm_message) {
					frappe.xcall("frappe_fcm.api.report_event", {
						message_id: data.fcm_message,
						event: "delivered",
					});
				}
			});
		},

		load_script(src) {
			return new Promise((resolve, reject) => {
				const script = document.createElement("script");
				script.src = src;
				script.onload = resolve;
				script.onerror = reject;
				document.head.appendChild(script);
			});
		},
	};

	$(document).on("app_ready", () => web_push.start());
}
