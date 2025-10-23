import base64
import hashlib
import hmac
import json
from http import HTTPStatus
from typing import Optional, Tuple

import frappe
from frappe import _
from werkzeug.wrappers import Response

from culinary_portal.tasks.sync_sales_orders import run_sales_order_sync
from culinary_portal.culinary_portal.woocommerce_api import (
	WC_RESOURCE_DELIMITER,
	parse_domain_from_url,
)


def validate_request() -> Tuple[bool, Optional[HTTPStatus], Optional[str]]:
	# Get relevant WooCommerce Server
	try:
		webhook_source_url = frappe.get_request_header("x-wc-webhook-source", "")
		print("\n\n\n DEBUG-1 webhook_source_url", webhook_source_url)
		wc_server = frappe.get_doc("WooCommerce Server", parse_domain_from_url(webhook_source_url))
		print("\n\n\n DEBUG-2 wc_server", wc_server)
	except Exception as e:
		print("\n\n\n DEBUG-3 Exception", e)
		return False, HTTPStatus.BAD_REQUEST, _("Missing Header")

	# Validate secret
	sig = base64.b64encode(
		hmac.new(wc_server.secret.encode("utf8"), frappe.request.data, hashlib.sha256).digest()
	)
	# if (
	# 	frappe.request.data
	# 	and not sig == frappe.get_request_header("x-wc-webhook-signature", "").encode()
	# ):
	# 	return False, HTTPStatus.UNAUTHORIZED, _("Unauthorized")
	print("\n\n\n DEBUG-3 frappe.set_user(wc_server.creation_user)", wc_server.creation_user)
	frappe.set_user(wc_server.creation_user)
	return True, None, None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def order_created(*args, **kwargs):
	"""
	Accepts payload data from Portal "Order Created" webhook
	"""
	valid, status, msg = validate_request()
	if not valid:
		return Response(response=msg, status=status)

	if frappe.request and frappe.request.data:
		try:
			order = json.loads(frappe.request.data)
			print("\n\n\n DEBUG-4 order", order)
		except ValueError:
			# woocommerce returns 'webhook_id=value' for the first request which is not JSON
			order = frappe.request.data
			print("\n\n\n DEBUG-5 order", order)
		event = frappe.get_request_header("x-wc-webhook-event")
		print("\n\n\n DEBUG-6 event", event)
	else:
		return Response(response=_("Missing Header"), status=HTTPStatus.BAD_REQUEST)

	if event == "created":
		webhook_source_url = frappe.get_request_header("x-wc-webhook-source", "")
		print("\n\n\n DEBUG-7 webhook_source_url", webhook_source_url)
		woocommerce_order_name = (
			f"{parse_domain_from_url(webhook_source_url)}{WC_RESOURCE_DELIMITER}{order['id']}"
		)
		print("\n\n\n DEBUG-8 woocommerce_order_name", woocommerce_order_name)
		frappe.enqueue(run_sales_order_sync, queue="long", woocommerce_order_name=woocommerce_order_name)
		return Response(status=HTTPStatus.OK)
	else:
		return Response(response=_("Event not supported"), status=HTTPStatus.BAD_REQUEST)
