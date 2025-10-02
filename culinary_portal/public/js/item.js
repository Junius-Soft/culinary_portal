frappe.ui.form.on("Item", {
	refresh(frm) {
		if (!frm.__wc_listener_bound) {
			frm.__wc_listener_bound = true;
			frappe.realtime.on("item_wc_id_updated", (data) => {
				if (data && data.doctype === "Item" && data.name === frm.doc.name) {
					if (data.field === "custom_woocommerce_id") {
						frm.set_value("custom_woocommerce_id", data.value);
						frm.refresh_field("custom_woocommerce_id");
						frm.trigger("refresh");
						// Gerekirse tam form yenileme:
						// frm.reload_doc();
					}
				}
			});
		}
	}
}); 