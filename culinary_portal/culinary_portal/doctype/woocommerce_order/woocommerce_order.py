# Copyright (c) 2025, culinary and contributors
# For license information, please see license.txt

import json
from dataclasses import dataclass
from typing import Dict, List

import frappe

from culinary_portal.culinary_portal.woocommerce_api import (
	WooCommerceAPI,
	WooCommerceResource,
	log_and_raise_error,
)
from culinary_portal.tasks.utils import APIWithRequestLogging


# Sipariş durum eşlemeleri (ERPNext <-> WooCommerce)
WC_ORDER_STATUS_MAPPING = {
	"Pending Payment": "pending",
	"On hold": "on-hold",
	"Failed": "failed",
	"Cancelled": "cancelled",
	"Processing": "processing",
	"Refunded": "refunded",
	"Shipped": "completed",
	"Ready for Pickup": "ready-pickup",
	"Picked up": "pickup",
	"Delivered": "delivered",
	"Processing LP": "processing-lp",
	"Draft": "checkout-draft",
	"Quote Sent": "gplsquote-req",
	"Trash": "trash",
	"Partially Shipped": "partial-shipped",
}
WC_ORDER_STATUS_MAPPING_REVERSE = {v: k for k, v in WC_ORDER_STATUS_MAPPING.items()}


@dataclass
class WooCommerceOrderAPI(WooCommerceAPI):
	"""WooCommerce Orders API wrapper (genişletilebilir)."""


class WooCommerceOrder(WooCommerceResource):
	"""
	Virtual DocType: WooCommerce Orders
	API üzerinden gerçek siparişi çeker ve kaydetmeden bellek üzerinde işler.
	"""

	doctype = "WooCommerce Order"
	resource: str = "orders"

	@staticmethod
	def _init_api() -> List[WooCommerceAPI]:
		"""
		WooCommerce Server kayıtlarına göre API istemcilerini hazırla
		"""
		wc_servers = frappe.get_all("WooCommerce Server")
		wc_servers = [frappe.get_doc("WooCommerce Server", s.name) for s in wc_servers]

		wc_api_list = [
			WooCommerceOrderAPI(
				api=APIWithRequestLogging(
					url=server.woocommerce_server_url,
					consumer_key=server.api_consumer_key,
					consumer_secret=server.api_consumer_secret,
					version="wc/v3",
					timeout=40,
				),
				woocommerce_server_url=server.woocommerce_server_url,
				woocommerce_server=server.name,
			)
			for server in wc_servers
			if server.enable_sync == 1
		]

		return wc_api_list

	# nosemgrep: keep args signature uyumlu
	@staticmethod
	def get_list(args):
		return WooCommerceOrder.get_list_of_records(args)

	# nosemgrep: keep args signature uyumlu
	@staticmethod
	def get_count(args) -> int:
		return WooCommerceOrder.get_count_of_records(args)

	def after_load_from_db(self, order: Dict):
		# Gerekirse ek alan işleme yapılabilir
		return order

