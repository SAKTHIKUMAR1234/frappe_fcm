from pathlib import Path

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

# The pinned Firebase JS SDK; the compat build works without a bundler.
FIREBASE_SDK_URL = "https://www.gstatic.com/firebasejs/13.0.0"
SERVICE_WORKER_PATH = "firebase-messaging-sw.js"
SERVICE_WORKER_FILE = Path(__file__).parent / "templates" / SERVICE_WORKER_PATH


def boot(bootinfo):
	"""`extend_bootinfo` hook: give a desk user the web push config. Without it the client JS does
	nothing: web push is off or not configured."""
	if frappe.session.user == "Guest":
		return
	config = frappe.get_cached_doc("FCM Settings").web_config
	if config:
		bootinfo.fcm_web_push = {"config": config, "sdk_url": FIREBASE_SDK_URL}


class ServiceWorkerPage(BaseRenderer):
	"""`page_renderer` hook: the Firebase messaging service worker at the site root, so its scope covers
	the whole site."""

	def can_render(self) -> bool:
		return self.path == SERVICE_WORKER_PATH

	def render(self) -> Response:
		script = SERVICE_WORKER_FILE.read_text().replace("__FIREBASE_SDK_URL__", FIREBASE_SDK_URL)
		response = Response(script, mimetype="text/javascript")
		response.headers["Cache-Control"] = "no-cache"
		return response
