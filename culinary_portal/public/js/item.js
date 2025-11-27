frappe.ui.form.on("Item", {
	refresh(frm) {
		// WooCommerce ID realtime güncelleme listener'ı
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

		// custom_portal_tax_rate alanının altına manuel tax_class güncelle butonu
		if (frm.fields_dict.custom_portal_tax_rate && !frm.is_new()) {
			const field = frm.fields_dict.custom_portal_tax_rate;

			if (!field._tax_button_added) {
				field._tax_button_added = true;

				const $btn = $(
					'<button class="btn btn-xs btn-secondary mt-2">' +
						__("Update Tax Class on Portal") +
					"</button>"
				);

				$btn.on("click", () => {
					if (!frm.doc.custom_woocommerce_id) {
						frappe.msgprint(
							__(
								"Item has no Portal ID. Please sync the product to Portal first."
							)
						);
						return;
					}

					frappe.call({
						method:
							"culinary_portal.custom_hooks.create_item.update_item_tax_class_in_woocommerce",
						args: {
							item_code: frm.doc.name,
						},
						freeze: true,
						freeze_message: __("Updating tax class on Portal..."),
						callback(r) {
							if (!r || !r.message) return;

							const res = r.message;
							if (res.status === "success") {
								frappe.msgprint(
									__(
										"Tax class updated on Portal: {0}",
										[res.tax_class || ""]
									)
								);
							} else {
								frappe.msgprint(
									res.message ||
										__(
											"Could not update tax class on Portal. Please check logs."
										)
								);
							}
						},
					});
				});

				field.$wrapper.append($btn);
			}
		}
	}
}); 