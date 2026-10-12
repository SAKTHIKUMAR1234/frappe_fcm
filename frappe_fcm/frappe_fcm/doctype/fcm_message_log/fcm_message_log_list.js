frappe.listview_settings["FCM Message Log"] = {
	add_fields: ["status", "delivered_on", "opened_on"],

	get_indicator(doc) {
		if (doc.status === "Failed") return [__("Failed"), "red", "status,=,Failed"];
		if (doc.opened_on) return [__("Opened"), "green", "opened_on,is,set"];
		if (doc.delivered_on) return [__("Delivered"), "blue", "delivered_on,is,set"];
		return [__("Sent"), "gray", "status,=,Sent"];
	},

	refresh(listview) {
		const labels = {
			sent: __("Sent"),
			delivered: __("Delivered"),
			opened: __("Opened"),
			failed: __("Failed"),
		};
		const filters = JSON.stringify(listview.get_filters_for_args());
		frappe.xcall("frappe_fcm.api.get_message_counts", { filters }, "GET").then((counts) => {
			const text = Object.entries(labels)
				.map(([key, label]) => `${label}: ${counts[key]}`)
				.join(" · ");
			listview.page.set_title_sub(frappe.utils.escape_html(text));
		});
	},
};
