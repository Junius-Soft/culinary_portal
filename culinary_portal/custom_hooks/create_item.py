import frappe
import requests
import json
from frappe.utils import get_url


def get_base_url():
	site_conf = getattr(frappe.local, "conf", {}) or {}
	return site_conf.get("base_url") or get_url()


def get_wo_url():
	site_conf = getattr(frappe.local, "conf", {}) or {}
	return site_conf.get("woocommerce_url") or get_url()


def get_consumer_key():
	site_conf = getattr(frappe.local, "conf", {}) or {}
	return site_conf.get("consumer_key") or ""


def get_consumer_secret():
	site_conf = getattr(frappe.local, "conf", {}) or {}
	return site_conf.get("consumer_secret") or ""


def get_wp_user():
	site_conf = getattr(frappe.local, "conf", {}) or {}
	return site_conf.get("wp_user") or ""


def get_wp_app_key():
	site_conf = getattr(frappe.local, "conf", {}) or {}
	return site_conf.get("wp_app_key") or ""


def get_vendor_category_id() -> int | None:
	"""Vendor Item Group'unun WooCommerce kategori ID'sini döndürür"""
	try:
		vendor_cat_id = frappe.db.get_value(
			"Item Group", {"name": "Vendor"}, "custom_woocommerce_category_id"
		)

		if not vendor_cat_id:
			frappe.msgprint(
				frappe._(
					"'Vendor' isimli ürün grubu bulunamadı veya WooCommerce kategori ID'si tanımlı değil. Lütfen 'Vendor' ürün grubunu oluşturun."
				),
				alert=True,
				indicator="red",
			)
			return None

		return int(vendor_cat_id) if vendor_cat_id else None

	except Exception as e:
		frappe.log_error(
			title="Vendor Category ID Error", message=f"Error: {str(e)}\n{frappe.get_traceback()}"
		)
		frappe.msgprint(frappe._("'Vendor' ürün grubunu oluşturun"), alert=True, indicator="red")
		return None


# def get_consumer_key():
#     woocommerce_server = frappe.get_value("WooCommerce Server", "www.temayolu.com", "api_consumer_key")

#     return woocommerce_server or ""


# def get_consumer_secret():
#     woocommerce_server = frappe.get_value("WooCommerce Server", "www.temayolu.com", "api_consumer_secret")
#     return woocommerce_server or ""
# Debug prints removed for security


def get_wc_category_id(category_name: str) -> int | None:
	"""Portal'de kategori adını arayıp id'sini döndürür; yoksa None."""
	if not category_name:
		return None
	try:
		url = f"{get_wo_url()}/wp-json/wc/v3/products/categories"
		resp = requests.get(
			url,
			auth=(get_consumer_key(), get_consumer_secret()),
			params={"search": category_name, "per_page": 1},
			headers={"Content-Type": "application/json"},
		)
		data = resp.json()
		if isinstance(data, list) and data:
			return data[0].get("id")
		if isinstance(data, dict):
			return data.get("id")
	except Exception:
		pass
	return None


def _fetch_wc_customer_meta_by_email(email: str, consumer_key: str, consumer_secret: str) -> dict:
	"""Verilen e‑posta için Portal customers API'den kullanıcının id ve meta_data'sını döndürür."""
	if not email:
		return {}
	url = f"{get_wo_url()}/wp-json/wc/v3/customers"
	try:
		resp = requests.get(
			url,
			auth=(consumer_key, consumer_secret),
			params={"email": email},
			headers={"Content-Type": "application/json"},
		)
		data = resp.json()
		print("\n\n\n DEBUGG---111---", resp)
		if isinstance(data, list) and data:
			customer = data[0]
		elif isinstance(data, dict):
			customer = data
		else:
			return {}
		return {
			"woocommerce_id": customer.get("id"),
			"email": customer.get("email"),
			"meta_data": customer.get("meta_data", []),
		}
	except Exception:
		return {}


def _extract_b2bking_customergroup(meta_data: list) -> str | None:
	"""Woo meta_data listesinden b2bking_customergroup value değerini çeker."""
	if not isinstance(meta_data, list):
		return None
	for entry in meta_data:
		if isinstance(entry, dict) and entry.get("key") == "b2bking_customergroup":
			return entry.get("value")
	return None


def _get_price_from_price_list(price_list_name: str, item_code: str) -> str | None:
	"""Verilen Price List adında (müşteri adı ile aynı) ilgili ürünün fiyatını döndürür."""
	if not price_list_name or not item_code:
		return None
	try:
		rate = frappe.db.get_value(
			"Item Price",
			{"price_list": price_list_name, "item_code": item_code},
			"price_list_rate",
		)
		if rate is None:
			rows = frappe.db.get_list(
				"Item Price",
				filters={"price_list": price_list_name, "item_code": item_code},
				fields=["price_list_rate"],
				order_by="modified desc",
				limit_page_length=1,
			)
			if rows:
				rate = rows[0].get("price_list_rate")
		if rate is None:
			return None
		return str(rate)
	except Exception:
		return None


def _get_standard_selling_price(item_code: str) -> str | None:
	"""'Standard Selling' Price List'ten fiyatı döndürür; yoksa Item.standard_rate'e düşer."""
	if not item_code:
		return None
	# Önce Standard Selling fiyat listesi
	rate = frappe.db.get_value(
		"Item Price",
		{"price_list": "Standard Selling", "item_code": item_code},
		"price_list_rate",
	)
	if rate is None:
		# Item.standard_rate fallback
		try:
			std_rate = frappe.db.get_value("Item", {"name": item_code}, "standard_rate")
			if std_rate is not None:
				rate = std_rate
		except Exception:
			rate = None
	return str(rate) if rate is not None else None


def collect_customer_b2bking_group_for_price_list(item_code: str, price_list_name: str) -> dict:
	"""Belirli bir Price List için o ürüne ait B2B group fiyatını döndürür.
	Sadece değiştirilen fiyat listesi için güncelleme yapar - performans optimizasyonu.
	"""
	consumer_key = get_consumer_key()
	consumer_secret = get_consumer_secret()

	# İlgili Customer'ı bul (Price List adı = Customer adı)
	customer = frappe.db.get_value(
		"Customer",
		{"name": price_list_name, "woocommerce_identifier": ["!=", ""]},
		["name", "woocommerce_identifier"],
		as_dict=True,
	)

	if not customer:
		return {"meta_data": []}

	email = customer.get("woocommerce_identifier")
	customer_price = _get_price_from_price_list(price_list_name, item_code)
	standard_price = _get_standard_selling_price(item_code)

	# Fiyat belirleme mantığı
	if customer_price:
		sale_price = customer_price
	elif standard_price:
		sale_price = standard_price
	else:
		return {"meta_data": []}

	# Regular price için standard fiyat kullan (yoksa sale price'ı kullan)
	regular_price = standard_price if standard_price else sale_price

	# WooCommerce'den customer meta data al
	wc_customer = _fetch_wc_customer_meta_by_email(email, consumer_key, consumer_secret)
	group_val = _extract_b2bking_customergroup(wc_customer.get("meta_data", [])) if wc_customer else None

	if not group_val:
		return {"meta_data": []}

	# Sadece bu grup için meta data oluştur
	meta_data = [
		{"key": f"b2bking_regular_product_price_group_{group_val}", "value": regular_price},
		{"key": f"b2bking_sale_product_price_group_{group_val}", "value": sale_price},
	]

	return {"meta_data": meta_data}


def get_uom_meta_data(item_code: str, item_data: dict | None = None, doc=None) -> list[dict]:
	"""Item için UOM meta_data bilgilerini döndürür"""
	uom_meta = []
	
	if not item_code:
		return uom_meta
	
	# product_uom - stock_uom değerini gönder
	stock_uom = None
	if doc and hasattr(doc, "stock_uom"):
		stock_uom = doc.stock_uom
	elif item_data:
		stock_uom = item_data.get("stock_uom")
	else:
		# Veritabanından al
		try:
			stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
		except Exception:
			pass
	
	if stock_uom:
		uom_meta.append({"key": "product_uom", "value": stock_uom})
		print(f"DEBUG: product_uom eklendi: {stock_uom}")
	
	# convertion_uom ve convertion_rate - UOM Conversion Detail'den al
	uoms_list = None
	
	# Önce doc'tan dene (child table'a doğrudan erişim)
	if doc and hasattr(doc, "uoms") and doc.uoms:
		uoms_list = doc.uoms
		print(f"DEBUG: doc.uoms bulundu, sayı: {len(uoms_list)}")
	# Doc'ta yoksa item_data'dan dene
	elif item_data and item_data.get("uoms"):
		uoms_list = item_data.get("uoms")
		print(f"DEBUG: item_data.uoms bulundu, sayı: {len(uoms_list)}")
	# Hala yoksa veritabanından çek
	else:
		try:
			uoms_list = frappe.db.get_all(
				"UOM Conversion Detail",
				filters={"parent": item_code, "parenttype": "Item"},
				fields=["uom", "conversion_factor"],
				order_by="idx asc",
				limit=1
			)
			if uoms_list:
				print(f"DEBUG: DB'den uoms bulundu, sayı: {len(uoms_list)}")
		except Exception as e:
			print(f"DEBUG: UOM DB sorgusu hatası: {e}")
	
	if uoms_list and len(uoms_list) > 0:
		first_uom = uoms_list[0]
		# Dict veya object olabilir
		uom_value = (
			first_uom.get("uom")
			if isinstance(first_uom, dict)
			else (first_uom.uom if hasattr(first_uom, "uom") else None)
		)
		conversion_factor = (
			first_uom.get("conversion_factor")
			if isinstance(first_uom, dict)
			else (first_uom.conversion_factor if hasattr(first_uom, "conversion_factor") else None)
		)
		
		if uom_value:
			uom_meta.append({"key": "convertion_uom", "value": uom_value})
			print(f"DEBUG: convertion_uom eklendi: {uom_value}")
		if conversion_factor is not None:
			uom_meta.append({"key": "convertion_rate", "value": str(conversion_factor)})
			print(f"DEBUG: convertion_rate eklendi: {conversion_factor}")
	else:
		print("DEBUG: UOM Conversion Detail bulunamadı")
	
	return uom_meta


def collect_customer_b2bking_groups_for_item(item_code: str) -> dict:
	"""Tüm müşteriler için, müşteri adıyla aynı Price List'ten bu ürüne ait fiyatı bulur;
	Woo'dan alınan b2bking group id ile birleştirip tek {"meta_data": [...]} döndürür.
	regular: Standard Selling fiyatı, sale: müşteri fiyatı (yoksa Standard Selling).
	Hiç fiyat yoksa uyarı gösterir.
	"""
	consumer_key = get_consumer_key()
	consumer_secret = get_consumer_secret()

	customers = frappe.db.get_list(
		"Customer",
		filters={"woocommerce_identifier": ["!=", ""]},
		fields=["name", "woocommerce_identifier"],
		limit_page_length=0,
	)

	seen_keys = set()
	merged: list[dict] = []
	has_any_price = False

	for cust in customers:
		email = cust.get("woocommerce_identifier")
		price_list_name = cust.get("name")
		customer_price = _get_price_from_price_list(price_list_name, item_code)
		standard_price = _get_standard_selling_price(item_code)

		# Fiyat belirleme mantığı
		if customer_price:
			sale_price = customer_price
			has_any_price = True
		elif standard_price:
			sale_price = standard_price
			has_any_price = True
		else:
			continue  # Bu müşteri için fiyat yok, atla

		# Regular price için standard fiyat kullan (yoksa sale price'ı kullan)
		regular_price = standard_price if standard_price else sale_price

		wc_customer = _fetch_wc_customer_meta_by_email(email, consumer_key, consumer_secret)
		group_val = _extract_b2bking_customergroup(wc_customer.get("meta_data", [])) if wc_customer else None
		if not group_val:
			continue

		entries = [
			{"key": f"b2bking_regular_product_price_group_{group_val}", "value": regular_price},
			{"key": f"b2bking_sale_product_price_group_{group_val}", "value": sale_price},
		]
		for m in entries:
			k = m.get("key")
			if k and k not in seen_keys:
				seen_keys.add(k)
				merged.append(m)

	# Hiç fiyat bulunamadıysa uyarı göster
	if not has_any_price:
		frappe.msgprint(frappe._("Product has no price"), alert=True)

	return {"meta_data": merged}


def sync_item_to_woocommerce(doctype: str, docname: str, skip_price_update: bool = False):
	"""Item veya Item Price'ı WordPress'e senkronize eder (queue'da çalışır)"""
	try:
		doc = frappe.get_doc(doctype, docname)
		
		# Sync tarafından oluşturulan/güncellenen kayıtları atla
		if getattr(doc.flags, "created_by_sync", None):
			return

		payload = doc.as_dict()
		consumer_key = get_consumer_key()
		consumer_secret = get_consumer_secret()

		# Item Price değişikliği ise - sadece ilgili B2B group'u güncelle
		if doc.doctype == "Item Price":
			item_code = payload.get("item_code")
			price_list_name = payload.get("price_list")

			# Item'ın WooCommerce ID'si yoksa işlem yapma
			existing_wc_id = frappe.db.get_value("Item", {"name": item_code}, "custom_woocommerce_id")
			if not existing_wc_id:
				print(f"DEBUG: Item {item_code} has no Portal ID, skipping Item Price sync")
				return

			# Sadece ilgili fiyat listesi için B2B group meta data al
			aggregated = collect_customer_b2bking_group_for_price_list(item_code, price_list_name)
			dynamic_meta = aggregated.get("meta_data", []) if isinstance(aggregated, dict) else []

			# UOM bilgilerini de ekle
			item_doc = frappe.get_doc("Item", item_code)
			uom_meta = get_uom_meta_data(item_code, item_data=item_doc.as_dict(), doc=item_doc)
			if uom_meta:
				# Mevcut meta_data'yı dict'e çevir (duplicate key kontrolü için)
				meta_dict = {}
				for m in dynamic_meta:
					key = m.get("key")
					if key:
						meta_dict[key] = m
				# UOM meta_data'larını ekle (varsa üzerine yaz)
				for uom_item in uom_meta:
					key = uom_item.get("key")
					if key:
						meta_dict[key] = uom_item
				# Dict'i tekrar listeye çevir
				dynamic_meta = list(meta_dict.values())
				print(f"DEBUG: Item Price güncellemesi - UOM meta_data eklendi, toplam: {len(dynamic_meta)}")

			if not dynamic_meta:
				print(f"DEBUG: No meta_data found for price list: {price_list_name}")
				return

			# Sadece meta_data güncellemesi için payload
			wc_payload = {"meta_data": dynamic_meta}

			# WooCommerce'e gönder
			send_to_woocommerce(wc_payload, consumer_key, consumer_secret, item_code, existing_wc_id)
			return

		# Item değişikliği ise - normal akış
		base_url = get_base_url()
		url = f"{get_wo_url()}/wp-json/wc/v3/products"
		print("\n\n\n DEBUG:0 base_url", base_url)

		# Item'ın WooCommerce ID'sini kontrol et
		existing_wc_id = None
		try:
			existing_wc_id = frappe.db.get_value(
				"Item", {"name": payload.get("item_code")}, "custom_woocommerce_id"
			)
		except Exception:
			existing_wc_id = None

		# Item Group'tan kategori ID'sini al
		category_id = None
		try:
			item_group_name = payload.get("item_group")
			if item_group_name:
				category_id = frappe.db.get_value(
					"Item Group", {"name": item_group_name}, "custom_woocommerce_category_id"
				)
				print(f"DEBUG: Item Group '{item_group_name}' -> category_id: {category_id}")
		except Exception as e:
			print(f"DEBUG: Error getting category_id from Item Group: {e}")
			category_id = None

		# Fiyat güncellemesi atlanacaksa, B2B fiyat meta_data'larını toplama
		dynamic_meta = []
		standard_price = None
		if skip_price_update:
			print("DEBUG: Fiyat güncellemesi atlanıyor - sadece fiyat dışı alanlar güncellenecek")
			# UOM bilgilerini al (fiyat dışı)
			uom_meta = get_uom_meta_data(payload.get("item_code"), item_data=payload, doc=doc)
			dynamic_meta = uom_meta if uom_meta else []
		else:
			# Ürüne bağlı birleşik meta_data (tek obje) al - tüm B2B grupları
			aggregated = collect_customer_b2bking_groups_for_item(payload.get("item_code"))
			dynamic_meta = aggregated.get("meta_data", []) if isinstance(aggregated, dict) else []

			# Standard Selling fiyat kontrolü
			standard_price = _get_standard_selling_price(payload.get("item_code"))
			print("\n\n\n DEBUG:1 standard_price", standard_price)

		# Status belirleme: disabled durumuna göre
		if payload.get("disabled", 0) == 1:
			status_value = "draft"
			print("DEBUG: Item disabled, status = draft")
		else:
			status_value = "publish"
			print("DEBUG: Item enabled, status = publish")

		# Fiyat kontrolü - eğer fiyat yoksa draft yap (sadece fiyat güncellemesi yapılıyorsa)
		if not skip_price_update:
			try:
				std_price_num = float(standard_price) if standard_price is not None else 0.0
			except Exception:
				std_price_num = 0.0
			if standard_price is None or std_price_num == 0.0:
				frappe.msgprint(frappe._("Product price not defined. Product will be added as Draft"), alert=True)
				status_value = "draft"

		# WooCommerce formatına dönüştür
		wc_payload = map_item_to_woocommerce(
			doc,
			payload,
			base_url,
			category_id,
			dynamic_meta,
			status_value=status_value,
			regular_price_override=str(standard_price) if (standard_price is not None and not skip_price_update) else None,
			skip_price_update=skip_price_update,
		)

		# WooCommerce'e gönder ve item_code ile existing_wc_id'yi geç
		send_to_woocommerce(wc_payload, consumer_key, consumer_secret, payload.get("item_code"), existing_wc_id)

		frappe.msgprint(frappe._("Item successfully synchronized to Portal"))
		
	except Exception as e:
		frappe.log_error(
			title="Sync Item to WooCommerce Error",
			message=f"DocType: {doctype}, DocName: {docname}\n{frappe.get_traceback()}",
		)


def handle_item_saved(doc, method=None):
	"""Item veya Item Price kaydedildiğinde queue'ya ekler"""
	print("\n\n\n DEBUG:0 handle_item_saved", doc)
	if doc.doctype == "Item Price":
		print("\n\n\n DEBUG:0 handle_item_saved Item Price", doc.as_dict())

	# Aynı istek içinde tekrar çalışmayı engelle
	if getattr(doc.flags, "culinary_wc_sync_ran", False):
		return
	doc.flags.culinary_wc_sync_ran = True

	# Sync tarafından oluşturulan/güncellenen kayıtları atla
	if getattr(doc.flags, "created_by_sync", None):
		return

	# Item güncellemesinde fiyat değişikliği kontrolü
	skip_price_update = False
	if doc.doctype == "Item":
		# Önceki değerleri kontrol et
		doc_before_save = getattr(doc, "_doc_before_save", None)
		if doc_before_save:
			# Fiyat ile ilgili alanların değişip değişmediğini kontrol et
			price_related_fields = ["standard_rate"]
			price_changed = False
			
			for field in price_related_fields:
				old_value = getattr(doc_before_save, field, None)
				new_value = getattr(doc, field, None)
				if old_value != new_value:
					price_changed = True
					break
			
			# Fiyat değişmemişse, sadece fiyat dışı güncelleme yap
			if not price_changed:
				skip_price_update = True
				print(f"DEBUG: Item {doc.name} - Fiyat değişmedi, sadece fiyat dışı alanlar güncellenecek")

	# Queue'ya ekle
	frappe.enqueue(
		"culinary_portal.custom_hooks.create_item.sync_item_to_woocommerce",
		doctype=doc.doctype,
		docname=doc.name,
		skip_price_update=skip_price_update,
		queue="default",
		timeout=300,  # 5 dakika timeout
		now=False,  # Arka planda çalışsın
	)
	print(f"DEBUG: {doc.doctype} {doc.name} queue'ya eklendi (skip_price_update={skip_price_update})")


def map_item_to_woocommerce(
	doc,
	item_data,
	base_url,
	category_id: int | None,
	meta_data: list[dict],
	status_value: str = "publish",
	regular_price_override: str | None = None,
	skip_price_update: bool = False,
):
	"""ERPNext Item verisini Portal formatına dönüştürür"""
	print("\n\n\n DEBUG:1 DOC NAME", doc)

	# UOM bilgilerini meta_data'ya ekle (fiyat güncellemesi atlanıyorsa zaten eklenmiş olabilir)
	item_code = item_data.get("item_code") or (doc.name if doc else None)
	
	# Eğer skip_price_update True ise, UOM zaten meta_data'da olabilir, tekrar eklemeye gerek yok
	if not skip_price_update:
		uom_meta = get_uom_meta_data(item_code, item_data=item_data, doc=doc)

		# Mevcut meta_data ile birleştir (duplicate key kontrolü ile)
		if uom_meta:
			# Mevcut meta_data'yı dict'e çevir (key bazlı erişim için)
			meta_dict = {}
			for m in (meta_data or []):
				key = m.get("key")
				if key:
					meta_dict[key] = m
			
			# UOM meta_data'larını ekle (varsa üzerine yaz)
			for uom_item in uom_meta:
				key = uom_item.get("key")
				if key:
					meta_dict[key] = uom_item
			
			# Dict'i tekrar listeye çevir
			meta_data = list(meta_dict.values())
			print(f"DEBUG: UOM meta_data eklendi, toplam meta_data sayısı: {len(meta_data)}")
		else:
			print("DEBUG: UOM meta_data eklenemedi")

	image_path = item_data.get("image", "") or ""
	images = []  # Default boş array
	if image_path:
		# Private files kontrolü - WooCommerce erişemez
		if "/private/" in image_path:
			print(f"⚠️ Private file atlandı (WooCommerce'deki eski görsel silinecek): {image_path}")
			images = []  # Boş array göndererek WooCommerce'deki görseli sil
		else:
			# Public file - WooCommerce'e gönder
			# Eğer image_path zaten tam URL ise (http:// veya https:// ile başlıyorsa), base_url ekleme
			if image_path.startswith(("http://", "https://")):
				image_url = image_path
			else:
				# Sadece path ise, base_url ekle
				image_url = f"{base_url}{image_path}"
			
			images = [
				{
					"src": image_url,
					"name": item_data.get("item_name", ""),
					"alt": item_data.get("item_name", ""),
				}
			]
			print(f"DEBUG: Image URL: {image_url}")

	# Categories başlangıcı - Item Group categories'ini ekle
	categories = []

	# 1. Vendor ana kategorisi - dinamik olarak al
	vendor_cat_id = get_vendor_category_id()
	if not vendor_cat_id:
		# Vendor kategori ID yoksa işlemi durdur
		frappe.throw(
			frappe._("Lütfen 'Vendor' ürün grubunu oluşturun ve WooCommerce kategori ID'sini tanımlayın")
		)

	categories.append({"id": vendor_cat_id})
	print(f"DEBUG: Added Vendor category ID: {vendor_cat_id}")

	# 2. Item Group kategori ID'sini ekle
	if category_id and str(category_id).isdigit():
		categories.append({"id": int(category_id)})
		print(f"DEBUG: Added Item Group category ID: {category_id}")

	# regular_price tercihi: override > item.standard_rate (sadece fiyat güncellemesi yapılıyorsa)
	regular_price_value = None
	if not skip_price_update:
		regular_price_value = (
			regular_price_override
			if regular_price_override is not None
			else str(item_data.get("standard_rate", "0.0"))
		)

	if doc.doctype == "Item":
		# Supplier categories'ini de ekle
		supplier_items = []
		if hasattr(doc, "supplier_items") and doc.supplier_items:
			# Supplier ID'lerini önce topla
			supplier_names = [item.supplier for item in doc.supplier_items if item.supplier]

			# Supplier bilgilerini tek sorguda çek
			supplier_data = {}
			if supplier_names:
				supplier_categories = frappe.db.get_list(
					"Supplier",
					filters={"name": ["in", supplier_names]},
					fields=["name", "custom_woocommerce_category_id", "custom_woocommerce_vendor_id"],
					limit_page_length=0,
				)
				supplier_data = {
					s.name: s.custom_woocommerce_category_id
					for s in supplier_categories
					if s.custom_woocommerce_category_id
				}
				print(f"\n\n\n DEBUG:1 supplier_data", supplier_data)

			# Supplier categories'ini categories'e ekle
			for supplier_name, supplier_cat_id in supplier_data.items():
				if supplier_cat_id and str(supplier_cat_id).isdigit():
					supplier_cat_int = int(supplier_cat_id)
					# Aynı kategori zaten ekli mi kontrol et
					existing_ids = [c.get("id") for c in categories]
					if supplier_cat_int not in existing_ids:
						categories.append({"id": supplier_cat_int, "parent": vendor_cat_id})
						print(
							f"DEBUG: Added Supplier category ID: {supplier_cat_int} for supplier: {supplier_name}"
						)

		print(f"\n\n\n DEBUG:1 Final categories", categories)

		wc_data = {
			"name": item_data.get("item_name", ""),
			"slug": item_data.get("item_code", ""),
			"type": "simple",
			"sku": item_data.get("item_code", ""),
			"description": item_data.get("description", ""),
			"short_description": item_data.get("custom_short_description", ""),
			"manage_stock": False,
			"stock_status": "instock",
			"status": status_value,
			"categories": categories,
			"images": images,
			"meta_data": meta_data or [],
		}

		# regular_price'ı sadece fiyat güncellemesi yapılıyorsa ekle
		if not skip_price_update and regular_price_value and regular_price_value != "0.0":
			wc_data["regular_price"] = regular_price_value
			print(f"DEBUG: regular_price WooCommerce'e gönderiliyor: {regular_price_value}")
		else:
			print("DEBUG: regular_price güncellemesi atlandı (skip_price_update=True)")
		
		return wc_data
	else:
		wc_data = {
			"meta_data": meta_data or [],
		}
		return wc_data


def update_dokan_post_author(item_code: str, wc_product_id: int):
	"""Item'ın supplier'ındaki vendor ID'yi Dokan API'sine post_author olarak gönderir"""
	try:
		# Item'ın supplier bilgisini al
		item_doc = frappe.get_doc("Item", item_code)

		if not hasattr(item_doc, "supplier_items") or not item_doc.supplier_items:
			print(f"DEBUG: Item {item_code} has no suppliers, skipping Dokan update")
			return

		# İlk supplier'ı al
		first_supplier = item_doc.supplier_items[0].supplier
		if not first_supplier:
			print(f"DEBUG: Item {item_code} has no valid supplier, skipping Dokan update")
			return

		# Supplier'ın vendor ID'sini al
		vendor_id = frappe.db.get_value("Supplier", first_supplier, "custom_woocommerce_vendor_id")

		# Eğer vendor ID yoksa, sync_dokan_vendor_id ile güncelle
		if not vendor_id:
			print(f"DEBUG: Supplier {first_supplier} has no vendor ID, syncing...")
			from culinary_portal.custom_hooks.sync_supplier import sync_dokan_vendor_id

			result = sync_dokan_vendor_id(first_supplier)

			if result.get("status") == "success":
				vendor_id = result.get("vendor_id")
				print(f"✅ Vendor ID synced for Supplier {first_supplier}: {vendor_id}")
			else:
				print(f"⚠️ Could not sync vendor ID for Supplier {first_supplier}: {result.get('message')}")
				return

		# Dokan API'sine istek at
		dokan_url = f"{get_wo_url()}/wp-json/dokan/v1/products/{wc_product_id}"
		wp_user = get_wp_user()
		wp_app_key = get_wp_app_key()

		if not wp_user or not wp_app_key:
			print("DEBUG: wp_user or wp_app_key not configured, skipping Dokan update")
			return

		dokan_payload = {"post_author": str(vendor_id)}

		response = requests.put(
			dokan_url,
			auth=(wp_user, wp_app_key),
			json=dokan_payload,
			headers={"Content-Type": "application/json"},
		)

		if response.status_code in (200, 201):
			print(f"✅ Dokan post_author güncellendi - Product ID: {wc_product_id}, Vendor ID: {vendor_id}")
		else:
			frappe.log_error(
				title="Dokan API Error",
				message=f"Status: {response.status_code}\nResponse: {response.text}\nProduct ID: {wc_product_id}, Vendor ID: {vendor_id}",
			)

	except Exception as e:
		frappe.log_error(
			title="Dokan Update Error",
			message=f"Item: {item_code}, WC Product ID: {wc_product_id}\n{frappe.get_traceback()}",
		)


def send_to_woocommerce(payload, consumer_key, consumer_secret, item_code, existing_wc_id=None):
	"""Portal API'sine veri gönderir ve dönen ID'yi Item'a kaydeder"""
	try:
		url = f"{get_wo_url()}/wp-json/wc/v3/products"

		# Meta_data kontrolü ve log
		if "meta_data" in payload:
			meta_data_count = len(payload.get("meta_data", []))
			print(f"DEBUG: send_to_woocommerce - meta_data sayısı: {meta_data_count}")
			# UOM meta_data'larını kontrol et
			uom_metas = [m for m in payload.get("meta_data", []) if m.get("key") in ["product_uom", "convertion_uom", "convertion_rate"]]
			if uom_metas:
				print(f"DEBUG: UOM meta_data'ları payload'da: {uom_metas}")
			else:
				print("DEBUG: UYARI - UOM meta_data'ları payload'da bulunamadı!")
			
			# Duplicate key kontrolü
			keys = [m.get("key") for m in payload.get("meta_data", []) if m.get("key")]
			duplicate_keys = [k for k in keys if keys.count(k) > 1]
			if duplicate_keys:
				print(f"⚠️ UYARI - Duplicate key'ler bulundu: {set(duplicate_keys)}")
		
		# Payload'ı logla (sadece meta_data varsa)
		if len(payload) == 1 and "meta_data" in payload:
			print(f"DEBUG: Payload (meta_data only): {json.dumps(payload, indent=2, ensure_ascii=False)[:500]}")

		# ID varsa güncelle, yoksa yeni oluştur
		if existing_wc_id:
			print(f"DEBUG: PUT isteği gönderiliyor - URL: {url}/{existing_wc_id}")
			response = requests.put(
				f"{url}/{existing_wc_id}",
				auth=(consumer_key, consumer_secret),
				json=payload,
				headers={"Content-Type": "application/json"},
			)
			print(f"🔄 Portal ürün güncellendi - ID: {existing_wc_id}, Status: {response.status_code}")
			wc_product_id = existing_wc_id
		else:
			response = requests.post(
				url,
				auth=(consumer_key, consumer_secret),
				json=payload,
				headers={"Content-Type": "application/json"},
			)
			print("➕ Yeni Portal ürün oluşturuluyor", response)
			wc_product_id = None

		if response.status_code in (200, 201):
			response_data = response.json()
			wc_product_id = response_data.get("id")
			
			# Response'daki meta_data'yı kontrol et
			if "meta_data" in response_data:
				response_meta_count = len(response_data.get("meta_data", []))
				print(f"DEBUG: Response meta_data sayısı: {response_meta_count}")
				# UOM meta_data'larını kontrol et
				response_uom_metas = [m for m in response_data.get("meta_data", []) if m.get("key") in ["product_uom", "convertion_uom", "convertion_rate"]]
				if response_uom_metas:
					print(f"DEBUG: Response'da UOM meta_data'ları: {response_uom_metas}")
				else:
					print("DEBUG: UYARI - Response'da UOM meta_data'ları yok!")
			else:
				print("DEBUG: UYARI - Response'da meta_data yok!")

			# Eğer yeni oluşturulduysa, Item'a WooCommerce ID'yi kaydet
			if wc_product_id and not existing_wc_id:
				try:
					frappe.db.set_value("Item", item_code, "custom_woocommerce_id", wc_product_id)
					frappe.db.commit()
					print(f"✅ Portal ID ({wc_product_id}) Item'a kaydedildi")
				except Exception as e:
					frappe.log_error(
						title="Item Portal ID Update Error",
						message=f"Item: {item_code}, WC ID: {wc_product_id}, Error: {str(e)}",
					)

			# Dokan API'sine post_author güncelleme isteği gönder
			# (sadece tam Item kaydı için, meta_data-only güncellemelerde çalıştırma)
			is_meta_only_update = len(payload) == 1 and "meta_data" in payload
			if wc_product_id and not is_meta_only_update:
				update_dokan_post_author(item_code, wc_product_id)

			# WooCommerce ürünü başarıyla oluştu/güncellendi, şimdi tax_class'ı Item.custom_portal_tax_rate'e göre ayarla
			if wc_product_id:
				try:
					print(
						f"DEBUG: send_to_woocommerce içinde tax_class enqueue ediliyor - "
						f"Item: {item_code}, WC ID: {wc_product_id}"
					)
					frappe.enqueue(
						"culinary_portal.custom_hooks.create_item.set_portal_tax_class_for_item",
						item_code=item_code,
						wc_product_id=wc_product_id,
						queue="default",
						timeout=120,
						now=False,
					)
					print(f"DEBUG: tax_class enqueue edildi - WC ID: {wc_product_id}, Item: {item_code}")
				except Exception:
					frappe.log_error(
						title="Portal Tax Class Enqueue Error",
						message=frappe.get_traceback(),
					)

			# frappe.msgprint(frappe._("Item successfully synchronized to Portal"))
			print("\n\n\n DEBUG:2 wc_product_id", payload)
		else:
			# Hata detaylarını logla
			error_message = f"Status: {response.status_code}\nResponse: {response.text}"
			print(f"❌ Portal API Hatası: {error_message}")
			try:
				error_json = response.json()
				print(f"DEBUG: Hata detayları (JSON): {json.dumps(error_json, indent=2, ensure_ascii=False)}")
			except Exception:
				pass
			frappe.log_error(
				title="Portal API Error",
				message=error_message,
			)

	except Exception as e:
		frappe.log_error(
			title="Portal Send Error",
			message=frappe.get_traceback(),
		)


def set_portal_tax_class_for_item(item_code: str, wc_product_id: int | str):
	"""Item.custom_portal_tax_rate alanına göre WooCommerce ürün tax_class alanını günceller.

	custom_portal_tax_rate:
	- %0  -> zero-rate
	- %7  -> standard
	- %19 -> reduced-rate
	"""
	try:
		if not item_code or not wc_product_id:
			print(f"DEBUG: set_portal_tax_class_for_item çağrıldı fakat item_code veya wc_product_id yok "
			      f"(item_code={item_code}, wc_product_id={wc_product_id})")
			return

		print(f"DEBUG: set_portal_tax_class_for_item başladı - Item: {item_code}, WC ID: {wc_product_id}")

		# Item üzerindeki custom_portal_tax_rate alanını al
		raw_rate = frappe.db.get_value("Item", item_code, "custom_portal_tax_rate")
		if raw_rate is None:
			print(f"DEBUG: Item {item_code} için custom_portal_tax_rate tanımlı değil, tax_class güncellenmeyecek")
			return

		# Değeri string olarak normalize et
		raw_str = str(raw_rate)
		# Örnek gelen değerler: "% 0", "%0", "0", "7", "% 19" vb.
		rate_str = raw_str.replace("%", "").strip()
		print(f"DEBUG: Item {item_code} custom_portal_tax_rate raw_value='{raw_str}', normalized='{rate_str}'")

		# Oranları tax_class ile eşleştir
		if rate_str in ("0", "0.0", "0,0"):
			tax_class = "zero-rate"
		elif rate_str in ("7", "7.0", "7,0"):
			tax_class = "standard"
		elif rate_str in ("19", "19.0", "19,0"):
			tax_class = "reduced-rate"
		else:
			# Beklenmeyen oranlar için şimdilik standard gönderelim
			tax_class = "standard"
			print(
				f"DEBUG: Item {item_code} için beklenmeyen tax rate değeri '{rate_str}', "
				f"tax_class=standard olarak gönderilecek"
			)

		consumer_key = get_consumer_key()
		consumer_secret = get_consumer_secret()

		# ID'yi string'e çevir, URL'de kullanacağız
		product_id = str(wc_product_id)

		url = f"{get_wo_url()}/wp-json/wc/v3/products/{product_id}"
		payload = {"tax_class": tax_class}
		print(f"DEBUG: WooCommerce tax_class isteği hazırlanıyor - URL: {url}, payload: {payload}")

		response = requests.put(
			url,
			auth=(consumer_key, consumer_secret),
			json=payload,
			headers={"Content-Type": "application/json"},
		)

		print(f"DEBUG: WooCommerce tax_class response status={response.status_code}, body={response.text}")

		if response.status_code in (200, 201):
			print(f"✅ WooCommerce ürün tax_class '{tax_class}' olarak güncellendi - ID: {product_id}")
		else:
			err_msg = f"Status: {response.status_code}\nResponse: {response.text}"
			print(f"❌ WooCommerce tax_class güncelleme hatası - ID: {product_id}, tax_class={tax_class} -> {err_msg}")
			frappe.log_error(
				title="WooCommerce Tax Class Error",
				message=err_msg,
			)
	except Exception:
		frappe.log_error(
			title="Portal Tax Class Error",
			message=frappe.get_traceback(),
		)


@frappe.whitelist()
def collect_customer_b2bking_groups() -> dict:
	"""Tüm müşterilerin b2bking group metasını tek bir objede birleştirip döndürür.
	Response: {"meta_data": [...]} (tek obje)
	"""
	consumer_key = get_consumer_key()
	consumer_secret = get_consumer_secret()

	customers = frappe.db.get_list(
		"Customer",
		filters={"woocommerce_identifier": ["!=", ""]},
		fields=["woocommerce_identifier"],
		limit_page_length=0,
	)

	seen_keys = set()
	merged: list[dict] = []

	for cust in customers:
		email = cust.get("woocommerce_identifier")
		meta = _fetch_wc_customer_meta_by_email(email, consumer_key, consumer_secret)
		group_val = _extract_b2bking_customergroup(meta.get("meta_data", [])) if meta else None
		customer_meta = []
		if group_val:
			customer_meta = [
				{"key": f"b2bking_regular_product_price_group_{group_val}", "value": "68"},
				{"key": f"b2bking_sale_product_price_group_{group_val}", "value": "60"},
			]
		for m in customer_meta:
			k = m.get("key")
			if k and k not in seen_keys:
				seen_keys.add(k)
				merged.append(m)

	return {"meta_data": merged}


@frappe.whitelist()
def sync_all_items_to_woocommerce():
	"""Tüm Item'ları Portal'e senkronize eder"""
	try:
		# Tüm aktif item'ları al (isteğe bağlı: disabled olanları dahil etmek için filtreyi kaldırabilirsiniz)
		items = frappe.db.get_list(
			"Item",
			filters={},  # Filtre: istersen {"disabled": 0} ekleyebilirsin
			fields=["name"],
			limit_page_length=0,
		)

		if not items:
			return {"status": "warning", "message": "Senkronize edilecek ürün bulunamadı"}

		success_count = 0
		error_count = 0
		error_items = []

		base_url = get_base_url()
		consumer_key = get_consumer_key()
		consumer_secret = get_consumer_secret()
		print("\n\n\n DEBUG:0 consumer_key", consumer_key)
		print("\n\n\n DEBUG:0 consumer_secret", consumer_secret)
		print("\n\n\n DEBUG:0 base_url", base_url)

		for item_dict in items:
			try:
				# Item'ı yükle
				item_doc = frappe.get_doc("Item", item_dict.name)

				# Sync bayrağını ayarla (tekrar çalışmasını engelle)
				item_doc.flags.culinary_wc_sync_ran = True

				payload = item_doc.as_dict()

				# WooCommerce ID'yi kontrol et
				existing_wc_id = frappe.db.get_value(
					"Item", {"name": payload.get("item_code")}, "custom_woocommerce_id"
				)

				# Category ID'yi al
				category_id = None
				item_group_name = payload.get("item_group")
				if item_group_name:
					category_id = frappe.db.get_value(
						"Item Group", {"name": item_group_name}, "custom_woocommerce_category_id"
					)

				# Meta data'yı topla
				aggregated = collect_customer_b2bking_groups_for_item(payload.get("item_code"))
				dynamic_meta = aggregated.get("meta_data", []) if isinstance(aggregated, dict) else []

				# Standard Selling fiyatı kontrol et
				standard_price = _get_standard_selling_price(payload.get("item_code"))

				# Status belirleme
				if payload.get("disabled", 0) == 1:
					status_value = "draft"
				else:
					status_value = "publish"

				# Fiyat kontrolü
				try:
					std_price_num = float(standard_price) if standard_price is not None else 0.0
				except Exception:
					std_price_num = 0.0

				if standard_price is None or std_price_num == 0.0:
					status_value = "draft"

				# WooCommerce payload'u oluştur
				wc_payload = map_item_to_woocommerce(
					item_doc,
					payload,
					base_url,
					category_id,
					dynamic_meta,
					status_value=status_value,
					regular_price_override=str(standard_price) if standard_price is not None else None,
				)

				# WooCommerce'e gönder
				url = f"{get_wo_url()}/wp-json/wc/v3/products"

				if existing_wc_id:
					response = requests.put(
						f"{url}/{existing_wc_id}",
						auth=(consumer_key, consumer_secret),
						json=wc_payload,
						headers={"Content-Type": "application/json"},
					)
				else:
					response = requests.post(
						url,
						auth=(consumer_key, consumer_secret),
						json=wc_payload,
						headers={"Content-Type": "application/json"},
					)

				if response.status_code in (200, 201):
					response_data = response.json()
					wc_product_id = response_data.get("id")

					# Yeni oluşturulduysa ID'yi kaydet
					if wc_product_id and not existing_wc_id:
						frappe.db.set_value("Item", item_dict.name, "custom_woocommerce_id", wc_product_id)

					# Dokan API'sine post_author güncelleme isteği gönder
					if wc_product_id:
						update_dokan_post_author(item_dict.name, wc_product_id)

					success_count += 1
				else:
					error_count += 1
					error_items.append(f"{item_dict.name} (HTTP {response.status_code})")

			except Exception as e:
				error_count += 1
				error_items.append(f"{item_dict.name} ({str(e)})")
				frappe.log_error(title=f"Item Sync Error - {item_dict.name}", message=frappe.get_traceback())

		# Değişiklikleri kaydet
		frappe.db.commit()

		# Sonuç mesajı
		message = f"✅ Başarılı: {success_count} ürün<br>❌ Hatalı: {error_count} ürün"
		if error_items and len(error_items) <= 10:
			message += f"<br><br>Hatalı ürünler:<br>{'<br>'.join(error_items)}"
		elif error_items:
			message += f"<br><br>İlk 10 hatalı ürün:<br>{'<br>'.join(error_items[:10])}"

		return {
			"status": "success" if error_count == 0 else "partial",
			"message": message,
			"success_count": success_count,
			"error_count": error_count,
		}

	except Exception as e:
		frappe.log_error(title="Bulk Item Sync Error", message=frappe.get_traceback())
		return {"status": "error", "message": f"Toplu senkronizasyon hatası: {str(e)}"}
