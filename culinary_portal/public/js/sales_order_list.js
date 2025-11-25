(() => {
	const namespace = frappe.provide("culinary_portal.sales_order");
	const extra_fields = ["custom_is_sub_sales_order", "custom_parent_sales_order"];

	// Alt siparis satirlarini ana siparis altinda gruplayan yonetici
	class SalesOrderHierarchy {
		constructor() {
			this.listview = null;
			this.expanded_parents = new Set();
			this.toggle_listener_attached = false;
			this.render_patched = false;
			this.styles_injected = false;
		}

		bind(listview) {
			if (!listview) {
				return;
			}

			const changed = this.listview !== listview;
			this.listview = listview;
			this.install_toggle_listener();

			if (changed) {
				this.patch_render();
			}

			this.decorate();
		}

		install_toggle_listener() {
			if (!this.listview || this.toggle_listener_attached) {
				return;
			}

			this.listview.$result.on("click", ".sales-order-toggle", (event) => {
				event.preventDefault();
				event.stopPropagation();
				const parent_name = event.currentTarget.getAttribute("data-parent");
				this.toggle_children(parent_name);
			});

			this.toggle_listener_attached = true;
		}

		patch_render() {
			if (!this.listview || this.render_patched) {
				return;
			}

			const original_render = this.listview.render;
			const manager = this;

			this.listview.render = function (...args) {
				const response = original_render.apply(this, args);
				frappe.after_ajax(() => manager.decorate());
				return response;
			};

			this.render_patched = true;
		}

		decorate() {
			if (!this.listview || !Array.isArray(this.listview.data)) {
				return;
			}

			this.ensure_styles();

			const docs = this.listview.data;
			this.reset_rows();

			const grouped = docs.reduce((acc, doc) => {
				if (!doc.custom_is_sub_sales_order || !doc.custom_parent_sales_order) {
					return acc;
				}

				(acc[doc.custom_parent_sales_order] ||= []).push(doc.name);
				return acc;
			}, {});

			Object.keys(grouped).forEach((parent_name) => {
				const $parent_row = this.get_row(parent_name);
				if (!$parent_row || !$parent_row.length) {
					return;
				}

				this.decorate_parent($parent_row, parent_name);
				this.decorate_children(grouped[parent_name], $parent_row, parent_name);
			});
		}

		ensure_styles() {
			if (this.styles_injected) {
				return;
			}

			const style_id = "sales-order-sub-style";
			if (document.getElementById(style_id)) {
				this.styles_injected = true;
				return;
			}

			const style = document.createElement("style");
			style.id = style_id;
			style.innerHTML = `
				.list-row.sales-order-sub .list-row-col.list-subject {
					padding-left: 1.75rem;
				}
				.list-row.sales-order-sub .list-row-col.list-subject::before {
					content: "";
					position: absolute;
					left: 0.75rem;
					top: 50%;
					width: 0.5rem;
					height: 0.5rem;
					border-radius: 50%;
					background: var(--gray-500, #999);
					transform: translateY(-50%);
				}
			`;

			document.head.appendChild(style);
			this.styles_injected = true;
		}

		reset_rows() {
			if (!this.listview) {
				return;
			}

			const $rows = this.listview.$result.find(".list-row");
			$rows.removeClass("sales-order-parent sales-order-sub");
			$rows.removeAttr("data-parent");
			$rows.show();
			$rows.find(".sales-order-toggle").remove();
		}

		decorate_parent($row, parent_name) {
			if ($row.find(".sales-order-toggle").length) {
				return;
			}

			$row.addClass("sales-order-parent");

			let $target_col = $row.find('.list-row-col[data-fieldname="name"]').first();
			if (!$target_col.length) {
				$target_col = $row.find(".list-row-col").first();
			}
			if (!$target_col.length) {
				$target_col = $row;
			}

			const $toggle = $(
				`<button type="button" class="btn btn-xs btn-default sales-order-toggle" data-parent="${parent_name}"></button>`
			);

			$toggle.text(this.expanded_parents.has(parent_name) ? "-" : "+");
			$target_col.prepend($toggle);
		}

		decorate_children(child_names, $parent_row, parent_name) {
			const expanded = this.expanded_parents.has(parent_name);
			let $last_inserted = $parent_row;

			child_names.forEach((child_name) => {
				const $child_row = this.get_row(child_name);
				if (!$child_row || !$child_row.length) {
					return;
				}

				$child_row.detach().insertAfter($last_inserted);
				$last_inserted = $child_row;

				$child_row
					.addClass("sales-order-sub")
					.attr("data-parent", parent_name)
					.toggle(expanded);
			});
		}

		toggle_children(parent_name) {
			if (!parent_name) {
				return;
			}

			const is_expanded = this.expanded_parents.has(parent_name);
			if (is_expanded) {
				this.expanded_parents.delete(parent_name);
				this.update_children_visibility(parent_name, false);
			} else {
				this.expanded_parents.add(parent_name);
				this.update_children_visibility(parent_name, true);
			}

			this.update_toggle_icon(parent_name);
		}

		update_children_visibility(parent_name, should_show) {
			const $children = this.listview.$result
				.find(".sales-order-sub")
				.filter((_, el) => $(el).attr("data-parent") === parent_name);
			$children.toggle(should_show);
		}

		update_toggle_icon(parent_name) {
			const $toggles = this.listview.$result
				.find(".sales-order-toggle")
				.filter((_, el) => el.getAttribute("data-parent") === parent_name);
			const symbol = this.expanded_parents.has(parent_name) ? "-" : "+";
			$toggles.text(symbol);
		}

		get_row(name) {
			if (!name) {
				return $();
			}

			return this.listview.$result.find(".list-row").filter((_, el) => {
				return $(el).find('[data-name="' + frappe.utils.escape_html(name) + '"]').length;
			});
		}
	}

	const manager = (namespace.manager = new SalesOrderHierarchy());

	const wait_for_settings = () =>
		new Promise((resolve) => {
			const check = () => {
				const settings =
					frappe.listview_settings && frappe.listview_settings["Sales Order"];
				if (settings) {
					resolve(settings);
				} else {
					setTimeout(check, 100);
				}
			};
			check();
		});

	const apply_customizations = (settings) => {
		if (!settings || settings.__culinary_portal_patched) {
			return;
			}

		settings.add_fields = Array.from(
			new Set([...(settings.add_fields || []), ...extra_fields])
		);

		const original_onload = settings.onload;
		settings.onload = function (listview) {
			if (original_onload) {
				original_onload.call(this, listview);
			}
			manager.bind(listview);
		};

		const original_refresh = settings.refresh;
		settings.refresh = function (listview) {
			if (original_refresh) {
				original_refresh.call(this, listview);
			}
			manager.decorate();
		};

		settings.__culinary_portal_patched = true;
	};

	wait_for_settings().then(apply_customizations);
})();
