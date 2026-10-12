### Frappe FCM

Firebase Cloud Messaging push for Frappe. Any app can install it to store users' device tokens, keep a per-user notification inbox (read and unread), and push to every device of a user or to a topic through FCM HTTP v1.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app frappe_fcm
```

### Setup

1. In the Firebase console, open Project settings > Service accounts and generate a new private key. Firebase gives a JSON key file.
2. Open **FCM Settings** (the Frappe FCM icon on the apps screen). Upload the key file to **Service Account Key File** as a private file. On save, the file must be a private service account key with `type`, `project_id`, `private_key`, `client_email` and `token_uri`. **Project ID** is read from the file.

Without a key file, nothing is sent and a warning is logged.

Web push (optional), for desk users:

1. In the Firebase console, open Project settings > General > Your apps and add a web app. Copy `apiKey`, `authDomain`, `messagingSenderId` and `appId` to FCM Settings. `projectId` is the Project ID of the key file.
2. Open Project settings > Cloud Messaging > Web Push certificates, generate a key pair and copy the public key to **VAPID Key**.
3. Set **Enable Web Push**.

When web push is on and configured, the desk loads the Firebase JS SDK compat build (pinned in `frappe_fcm.web_push.FIREBASE_SDK_URL`), registers the service worker `/firebase-messaging-sw.js` and, after the user allows notifications (at the first click), registers the browser token as an FCM Device (`platform` Web, `app_name` Desk). Otherwise the client JS does nothing.

### Data

| DocType | Use |
| --- | --- |
| **FCM Settings** | The service account key file (private), the project id and the web push config. |
| **FCM Device** | One row per FCM token: `user`, `token`, `platform` (Android, iOS or Web), `app_name`, `app_version`, `last_seen`, `enabled`. |
| **FCM Notification** | The user's inbox: `user`, `app_name`, `title`, `body`, `data` (JSON), `read`, `message_id` (first push), `reference_doctype`, `reference_name`. A user reads only their own rows (also through `/api/resource`); a System Manager reads all. |
| **FCM Message Log** | One row per send to one device or topic: `target` (token or topic), `user`, `title`, `body`, `data`, `status` (Sent or Failed), `message_id`, `error`, `delivered_on`, `opened_on`. The list shows the counts of sent, delivered, opened and failed messages of the current filters. Log Settings clears rows older than 30 days. |

### Python API

| Function | Use |
| --- | --- |
| `frappe_fcm.devices.register_device(user, token, platform, app_name, app_version)` | Enable the token for the user. One row per token: a token of another user moves to `user`. Commits the open transaction first. |
| `frappe_fcm.devices.remove_device(token)` | Delete the device. |
| `frappe_fcm.devices.disable_devices(user, app_name=None)` | Stop pushes to the user's devices, for example at logout. |
| `frappe_fcm.push.send_to_users(users, title, body, data=None, app_name=None)` | Queue a push (queue `short`, after commit) to the enabled devices of the users. |
| `frappe_fcm.push.send_to_topic(topic, title, body, data=None)` | Queue a push to a topic. |
| `frappe_fcm.push.deliver_to_users(users, push, app_name=None)` | Send a `Push` now and return the message ids. |
| `frappe_fcm.push.deliver_to_topic(topic, push)` | Send a `Push` now and return the message id. |

`send_to_*` also take `data_only=True` (no `notification` block; title and body go in `data`) and `collapse_key`. Data values are sent as text; other values are sent as JSON text.

Inbox, in `frappe_fcm.notifications`:

| Function | Use |
| --- | --- |
| `notify(user, title, body, data=None, app_name=None, **values)` | Add an FCM Notification. After commit it is pushed (queue `short`) to the user's enabled devices of `app_name`, and the first message id is kept. A row with `flags.skip_push` is not pushed. |
| `get_notifications(user, app_name=None, filters=None, start=0, page_length=20, fields=FIELDS)` | The user's rows, newest first. |
| `count_notifications(user, app_name=None, filters=None)` | The number of rows. |
| `mark_read(user, name=None, app_name=None)` | Mark one row read, or all unread rows without `name`. A row of another user or app: `DoesNotExistError`. |
| `find_by_message_id(user, message_id, app_name=None)` | The row of a push message id, else of that name. |

An app changes the push of its notifications with the hook `fcm_push = {"<app_name>": "dotted.path"}`. The function gets the FCM Notification and returns a `Push`, or None to send nothing (for example when the user may no longer get it). Without the hook, the push has the title and body, and `data` plus `notification` (the row name).

When FCM says the token is dead, the device is deleted: `UNREGISTERED`, `NOT_FOUND`, or `INVALID_ARGUMENT` whose `fieldViolations` name `message.token`. Other errors, such as an `INVALID_ARGUMENT` for the message, keep the device. Each send writes an FCM Message Log.

### Tracking

The data of each message has `fcm_message`, the name of its FCM Message Log. A client reports events with `frappe_fcm.api.report_event`:

| Event | Client | Sets |
| --- | --- | --- |
| `delivered` | A mobile app or the desk when the message arrives; the service worker for a background web message. | `delivered_on` |
| `opened` | A mobile app when the user opens the notification; the service worker on a click. | `opened_on` and, if empty, `delivered_on` |

The first time of each event is kept. A failed send records `status` Failed and the `error`.

Mobile apps need no code in this app. They keep the native Firebase config themselves and use `register_device` and `report_event`.

### Endpoints

| Method | Use |
| --- | --- |
| `frappe_fcm.api.register_device` (POST) | Arguments `token`, `platform`, `app_name`, `app_version`. Registers the device for the session user. Returns the device name. |
| `frappe_fcm.api.remove_device` (POST) | Argument `token`. Deletes the session user's device. A device of another user: 403. |
| `frappe_fcm.api.get_notifications` (GET) | Arguments `app_name`, `start`, `page_length` (at most 100). The session user's rows. |
| `frappe_fcm.api.mark_read` (POST) | Arguments `name`, `app_name`. A row of another user: 404. |
| `frappe_fcm.api.report_event` (GET or POST) | Arguments `message_id` (the `fcm_message` of the data, or the FCM message id in full or after `/messages/`) and `event` (`delivered` or `opened`). A message of another user: 403. GET is for the service worker, which has no CSRF token. |
| `frappe_fcm.api.get_message_counts` (GET) | Argument `filters` (list filters of FCM Message Log). Returns `sent`, `delivered`, `opened` and `failed`. Needs read access to FCM Message Log. |

Guests cannot call them.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/frappe_fcm
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
