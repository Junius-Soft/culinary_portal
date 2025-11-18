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


def extract_meta_value(meta_data, key):
	"""
	meta_data listesinden belirli bir key'in value'sunu çıkarır
	"""
	for item in meta_data:
		if item.get("key") == key:
			return item.get("value", "")
	return ""


def map_wordpress_data_to_customer(user_data, customer_doc):
	"""
	WordPress user data'sını Customer doc'a map eder
	"""
	# Ana alanlar
	customer_doc.custom_role = user_data.get("role", "")
	customer_doc.username = user_data.get("username", "")
	customer_doc.is_paying_customer = 1 if user_data.get("is_paying_customer") else 0
	customer_doc.avatar_url = user_data.get("avatar_url", "")
	
	# Meta data alanları
	meta_data = user_data.get("meta_data", [])
	
	customer_doc.entry_id = extract_meta_value(meta_data, "entry_id")
	customer_doc.twitter = extract_meta_value(meta_data, "twitter")
	customer_doc.facebook = extract_meta_value(meta_data, "facebook")
	customer_doc.additional_profile_urls = extract_meta_value(meta_data, "additional_profile_urls")
	customer_doc.wc_last_active = extract_meta_value(meta_data, "wc_last_active")
	customer_doc.address_street = extract_meta_value(meta_data, "address_street")
	customer_doc.address_apartment = extract_meta_value(meta_data, "address_apartment")
	customer_doc.address_city = extract_meta_value(meta_data, "address_city")
	customer_doc.address_state = extract_meta_value(meta_data, "address_state")
	customer_doc.address_zip = extract_meta_value(meta_data, "address_zip")
	customer_doc.address_country = extract_meta_value(meta_data, "address_country")
	
	# İngilizce custom field'lar (resimdeki alan isimleri)
	customer_doc.custom_company_name = extract_meta_value(meta_data, "company_name")
	customer_doc.custom_reference = extract_meta_value(meta_data, "reference")
	customer_doc.custom_telephone_number = extract_meta_value(meta_data, "user_phone")
	customer_doc.custom_company_type = extract_meta_value(meta_data, "company_type")
	customer_doc.custom_tax_id_number = extract_meta_value(meta_data, "steuernummer")
	customer_doc.custom_vat_identification = extract_meta_value(meta_data, "umsatzsteuer")
	customer_doc.custom_company_representive_name = extract_meta_value(meta_data, "firmenvertreter_name")
	customer_doc.custom_company_representive_surname = extract_meta_value(meta_data, "firmenvertreter_surname")
	customer_doc.custom_company_representive_phone = extract_meta_value(meta_data, "firmenvertreter_phone")
	customer_doc.custom_contact_person = extract_meta_value(meta_data, "kontaktperson__name")
	customer_doc.custom_contact_person_email = extract_meta_value(meta_data, "kontaktperson__email")
	customer_doc.custom_contact_person_phone = extract_meta_value(meta_data, "kontaktperson__phone")
	customer_doc.custom_iban = extract_meta_value(meta_data, "iban")
	customer_doc.custom_bic = extract_meta_value(meta_data, "bic")
	customer_doc.custom_date_of_issue = extract_meta_value(meta_data, "ausstellungsdatum")
	customer_doc.custom_expiry_date = extract_meta_value(meta_data, "ablaufdatum")
	customer_doc.custom_operating_form = extract_meta_value(meta_data, "betriebsform")
	
	return customer_doc


def create_or_update_customer(user_data, is_new_customer=False):
	"""
	WordPress user data'sından Customer oluşturur veya günceller
	
	Args:
		user_data: WordPress'ten gelen user data
		is_new_customer: True ise B2B Group hook'u çalışır
	
	Returns:
		Tuple: (customer_name, success_message)
	"""
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
	
	print(f"\n\n\n DEBUG-COMMON-1 customer_name: {customer_name}, email: {email}, id: {user_id}")
	
	if not customer_name or not email:
		raise ValueError("Customer name veya email eksik!")
	
	# Email ile mevcut Customer kontrolü
	existing_customer = frappe.db.exists("Customer", {"woocommerce_identifier": email})
	
	if existing_customer:
		print(f"\n\n\n DEBUG-COMMON-2 Mevcut Customer bulundu: {existing_customer}")
		# Mevcut customer'ı güncelle
		customer_doc = frappe.get_doc("Customer", existing_customer)
		
		# B2B Group hook'unu atla (sadece yeni customer'da çalışsın)
		customer_doc.flags.skip_b2b_group_hook = True
		customer_doc.flags.ignore_permissions = True
		customer_doc.flags.ignore_validate = True
		customer_doc.flags.ignore_mandatory = True
		customer_doc.flags.ignore_links = True
		
		customer_doc.customer_name = customer_name
		customer_doc.custom_portal_user_id = user_id
		
		# Tüm WordPress data'sını map et
		customer_doc = map_wordpress_data_to_customer(user_data, customer_doc)
		
		customer_doc.save(ignore_permissions=True)
		frappe.db.commit()
		print(f"\n\n\n DEBUG-COMMON-3 Customer güncellendi: {existing_customer}")
		
		return existing_customer, "güncellendi"
	else:
		# Yeni Customer oluştur
		print("\n\n\n DEBUG-COMMON-4 Yeni Customer oluşturuluyor...")
		customer_doc = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": customer_name,
			"woocommerce_identifier": email,
			"custom_portal_user_id": user_id,
			"disabled":1,
		})
		
		# Tüm WordPress data'sını map et
		customer_doc = map_wordpress_data_to_customer(user_data, customer_doc)
		
		# Flag'leri ayarla
		customer_doc.flags.ignore_permissions = True
		customer_doc.flags.ignore_validate = True
		customer_doc.flags.ignore_mandatory = True
		customer_doc.flags.ignore_links = True
		
		# YENİ customer için B2B Group hook'u çalışacak mı?
		if not is_new_customer:
			customer_doc.flags.skip_b2b_group_hook = True
			print("\n\n\n DEBUG-COMMON-5 B2B hook atlanacak")
		else:
			print("\n\n\n DEBUG-COMMON-5 B2B hook çalışacak")
		
		customer_doc.insert(ignore_permissions=True)
		frappe.db.commit()
		print(f"\n\n\n DEBUG-COMMON-6 Yeni Customer oluşturuldu: {customer_doc.name}")
		
		return customer_doc.name, "oluşturuldu"


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
			
			# Ortak fonksiyon ile Customer oluştur/güncelle (is_new_customer=True → B2B hook çalışacak)
			customer_name, action = create_or_update_customer(user_data, is_new_customer=True)
			print(f"\n\n\n DEBUG-USER-FINAL Customer {action}: {customer_name}")
			
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


@frappe.whitelist(allow_guest=True, methods=["POST"])
def user_updated(*args, **kwargs):
	"""
	WordPress'te user güncellendiğinde tetiklenen webhook endpoint'i
	"""
	print("\n\n\n ========== USER UPDATED WEBHOOK BAŞLADI ==========")
	
	# Request data'yı göster
	if frappe.request and frappe.request.data:
		print("\n\n\n DEBUG-UPDATE-2 Raw Request Data:", frappe.request.data)
		
		try:
			user_data = json.loads(frappe.request.data)
			print("\n\n\n DEBUG-UPDATE-3 Parsed User Data (JSON):")
			print(json.dumps(user_data, indent=2, ensure_ascii=False))
		except ValueError:
			# WordPress webhook'un ilk test isteği 'webhook_id=value' formatında gelir (JSON değil)
			print("\n\n\n DEBUG-UPDATE-3.1 İlk test isteği (webhook_id), başarılı kabul edildi")
			return Response(status=HTTPStatus.OK)
		
		try:
			# Ortak fonksiyon ile Customer oluştur/güncelle (is_new_customer=False → B2B hook atlanacak)
			# Eğer Customer yoksa oluşturulacak (user_created gibi)
			customer_name, action = create_or_update_customer(user_data, is_new_customer=False)
			print(f"\n\n\n DEBUG-UPDATE-FINAL Customer {action}: {customer_name}")
			
			print("\n\n\n ========== USER UPDATED WEBHOOK BİTTİ ==========")
			return Response(status=HTTPStatus.OK)
		except Exception as e:
			print(f"\n\n\n DEBUG-UPDATE-ERROR Exception: {str(e)}")
			frappe.log_error(
				title="User Update Webhook Exception",
				message=frappe.get_traceback()
			)
			return Response(response=_("Internal Server Error"), status=HTTPStatus.INTERNAL_SERVER_ERROR)
	else:
		print("\n\n\n DEBUG-UPDATE-ERROR: Request data bulunamadı!")
		return Response(response=_("No data received"), status=HTTPStatus.BAD_REQUEST)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def attach_pdf_to_customer(*args, **kwargs):
	"""
	PDF dosyasını URL'den indirip Customer'a attach eder
	Body format:
	{
		"pdf_url": "https://example.com/file.pdf",
		"signer_email": "customer@example.com",
		"document_title": "Document Title"
	}
	"""
	print("\n\n\n ========== ATTACH PDF TO CUSTOMER BAŞLADI ==========")
	
	if not frappe.request or not frappe.request.data:
		print("\n\n\n DEBUG-PDF-ERROR: Request data bulunamadı!")
		return Response(response=_("No data received"), status=HTTPStatus.BAD_REQUEST)
	
	try:
		# Request body'yi parse et
		data = json.loads(frappe.request.data)
		print("\n\n\n DEBUG-PDF-1 Parsed Data:")
		print(json.dumps(data, indent=2, ensure_ascii=False))
		
		pdf_url = data.get("pdf_url")
		signer_email = data.get("signer_email")
		document_title = data.get("document_title")
		
		# Gerekli alanları kontrol et
		if not pdf_url or not signer_email or not document_title:
			print("\n\n\n DEBUG-PDF-ERROR: Gerekli alanlar eksik!")
			return Response(
				response=_("Missing required fields: pdf_url, signer_email, document_title"),
				status=HTTPStatus.BAD_REQUEST
			)
		
		print(f"\n\n\n DEBUG-PDF-2 pdf_url: {pdf_url}")
		print(f"\n\n\n DEBUG-PDF-3 signer_email: {signer_email}")
		print(f"\n\n\n DEBUG-PDF-4 document_title: {document_title}")
		
		# Customer'ı bul
		customer = frappe.db.get_value(
			"Customer",
			{"woocommerce_identifier": signer_email},
			["name", "customer_name"],
			as_dict=True
		)
		
		if not customer:
			print(f"\n\n\n DEBUG-PDF-ERROR: Customer bulunamadı: {signer_email}")
			return Response(
				response=_("Customer not found with woocommerce_identifier: {0}").format(signer_email),
				status=HTTPStatus.NOT_FOUND
			)
		
		print(f"\n\n\n DEBUG-PDF-5 Customer bulundu: {customer.name}")
		
		# URL'i link olarak attach et
		print(f"\n\n\n DEBUG-PDF-6 URL link olarak attach ediliyor: {pdf_url}")
		
		file_name = f"{document_title}.pdf"
		
		# File doc oluştur ve validation'ı bypass et
		file_doc = frappe.new_doc("File")
		file_doc.file_name = file_name
		file_doc.file_url = pdf_url
		file_doc.attached_to_doctype = "Customer"
		file_doc.attached_to_name = customer.name
		file_doc.is_private = 0
		file_doc.flags.ignore_permissions = True
		file_doc.flags.ignore_validate = True
		file_doc.flags.ignore_mandatory = True
		file_doc.insert()
		frappe.db.commit()
		
		print(f"\n\n\n DEBUG-PDF-7 Link kaydedildi: {file_doc.name}")
		print("\n\n\n ========== ATTACH PDF TO CUSTOMER BİTTİ ==========")
		
		return Response(
			response=json.dumps({
				"success": True,
				"message": _("PDF link successfully attached to customer"),
				"customer": customer.name,
				"file": file_doc.name,
				"file_url": file_doc.file_url
			}),
			status=HTTPStatus.OK,
			content_type="application/json"
		)
		
	except json.JSONDecodeError as e:
		print(f"\n\n\n DEBUG-PDF-ERROR JSON Parse Hatası: {str(e)}")
		frappe.log_error(
			title="Attach PDF JSON Parse Error",
			message=f"Error: {str(e)}\nData: {frappe.request.data}"
		)
		return Response(response=_("Invalid JSON"), status=HTTPStatus.BAD_REQUEST)
	
	except Exception as e:
		print(f"\n\n\n DEBUG-PDF-ERROR Exception: {str(e)}")
		frappe.log_error(
			title="Attach PDF Exception",
			message=frappe.get_traceback()
		)
		return Response(
			response=_("Internal Server Error: {0}").format(str(e)),
			status=HTTPStatus.INTERNAL_SERVER_ERROR
		)
