import frappe


def run_item_sync(woocommerce_product_name: str):
	"""
	Attempt to sync/create the Item for a given WooCommerce product name.
	If the upstream woocommerce_fusion app is installed, delegate to it.
	Otherwise, log and safely skip so Sales Order sync can proceed.
	"""
	try:
		from woocommerce_fusion.tasks.sync_items import run_item_sync as upstream_run_item_sync
	except Exception:
		frappe.logger().info(
			f"[culinary_portal] Skipping item sync (upstream not available) for {woocommerce_product_name}"
		)
		return None

	# Delegate to upstream implementation
	return upstream_run_item_sync(woocommerce_product_name=woocommerce_product_name)








