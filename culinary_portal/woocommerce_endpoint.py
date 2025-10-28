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


@frappe.whitelist(allow_guest=True, methods=["POST"])
def user_created(*args, **kwargs):
	"""
	WordPress'te user oluşturulduğunda tetiklenen webhook endpoint'i
	"""
	print("\n\n\n ========== USER CREATED WEBHOOK BAŞLADI ==========")
	
	# Request data'yı göster
	if frappe.request and frappe.request.data:
		print("\n\n\n DEBUG-USER-2 Raw Request Data:", frappe.request.data)
		
		try:
			user_data = json.loads(frappe.request.data)
			print("\n\n\n DEBUG-USER-3 Parsed User Data (JSON):")
			print(json.dumps(user_data, indent=2, ensure_ascii=False))
			
			# Gerekli alanları al
			username = user_data.get("username", "")
			email = user_data.get("email", "")
			user_id = user_data.get("id")
			first_name = user_data.get("first_name", "").strip()
			last_name = user_data.get("last_name", "").strip()
			
			# Customer name oluştur: first_name + last_name veya username
			if first_name and last_name:
				customer_name = f"{first_name} {last_name}"
			elif first_name:
				customer_name = first_name
			elif last_name:
				customer_name = last_name
			else:
				customer_name = username
			
			print(f"\n\n\n DEBUG-USER-4 Mapping - customer_name: {customer_name}, email: {email}, id: {user_id}")
			
			if not customer_name or not email:
				print("\n\n\n DEBUG-USER-ERROR: Customer name veya email eksik!")
				return Response(response=_("Missing required fields"), status=HTTPStatus.BAD_REQUEST)
			
			# Email ile mevcut Customer kontrolü
			existing_customer = frappe.db.exists("Customer", {"woocommerce_identifier": email})
			
			if existing_customer:
				print(f"\n\n\n DEBUG-USER-5 Mevcut Customer bulundu: {existing_customer}")
				# Mevcut customer'ı güncelle
				customer_doc = frappe.get_doc("Customer", existing_customer)
				customer_doc.customer_name = customer_name
				customer_doc.custom_portal_user_id = user_id
				customer_doc.save(ignore_permissions=True)
				frappe.db.commit()
				print(f"\n\n\n DEBUG-USER-6 Customer güncellendi: {existing_customer}")
			else:
				# Yeni Customer oluştur
				print("\n\n\n DEBUG-USER-7 Yeni Customer oluşturuluyor...")
				customer_doc = frappe.get_doc({
					"doctype": "Customer",
					"customer_name": customer_name,
					"woocommerce_identifier": email,
					"custom_portal_user_id": user_id,					
				})
				customer_doc.insert(ignore_permissions=True)
				frappe.db.commit()
				print(f"\n\n\n DEBUG-USER-8 Yeni Customer oluşturuldu: {customer_doc.name}")
			
			print("\n\n\n ========== USER CREATED WEBHOOK BİTTİ ==========")
			return Response(status=HTTPStatus.OK)
			
		except ValueError as e:
			print("\n\n\n DEBUG-USER-ERROR JSON Parse Hatası:", e)
			frappe.log_error(
				title="User Webhook JSON Parse Error",
				message=f"Error: {str(e)}\nData: {frappe.request.data}"
			)
			return Response(response=_("Invalid JSON"), status=HTTPStatus.BAD_REQUEST)
		except Exception as e:
			print(f"\n\n\n DEBUG-USER-ERROR Exception: {str(e)}")
			frappe.log_error(
				title="User Webhook Exception",
				message=frappe.get_traceback()
			)
			return Response(response=_("Internal Server Error"), status=HTTPStatus.INTERNAL_SERVER_ERROR)
	else:
		print("\n\n\n DEBUG-USER-ERROR: Request data bulunamadı!")
		return Response(response=_("No data received"), status=HTTPStatus.BAD_REQUEST)
