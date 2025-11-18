import frappe
import requests
import json
from frappe.utils import get_url


def get_base_url():
    site_conf = getattr(frappe.local, "conf", {}) or {}
    return (
        site_conf.get("base_url")
        or get_url()
    )


def get_wo_url():
    site_conf = getattr(frappe.local, "conf", {}) or {}
    return (
        site_conf.get("woocommerce_url")
        or get_url()
    )


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
            "Item Group",
            {"name": "Vendor"},
            "custom_woocommerce_category_id"
        )
        
        if not vendor_cat_id:
            frappe.msgprint(
                frappe._("'Vendor' isimli ürün grubu bulunamadı veya WooCommerce kategori ID'si tanımlı değil. Lütfen 'Vendor' ürün grubunu oluşturun."),
                alert=True,
                indicator="red"
            )
            return None
            
        return int(vendor_cat_id) if vendor_cat_id else None
        
    except Exception as e:
        frappe.log_error(
            title="Vendor Category ID Error",
            message=f"Error: {str(e)}\n{frappe.get_traceback()}"
        )
        frappe.msgprint(
            frappe._("'Vendor' ürün grubunu oluşturun"),
            alert=True,
            indicator="red"
        )
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
        as_dict=True
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


def sync_item_price_to_woocommerce(item_code: str, price_list_name: str):
    """Item Price değişikliğini WooCommerce'e senkronize eder (queue'da çalışır)"""
    logger = frappe.logger("culinary_portal", allow_site=True)
    try:
        logger.info(f"sync_item_price_to_woocommerce başladı - Item: {item_code}, Price List: {price_list_name}")
        frappe.set_user("Administrator")
        
        # Item'ın WooCommerce ID'si yoksa işlem yapma
        existing_wc_id = frappe.db.get_value("Item", {"name": item_code}, "custom_woocommerce_id")
        if not existing_wc_id:
            logger.info(f"Item {item_code} has no Portal ID, skipping Item Price sync")
            return
        
        # Sadece ilgili fiyat listesi için B2B group meta data al
        aggregated = collect_customer_b2bking_group_for_price_list(item_code, price_list_name)
        dynamic_meta = aggregated.get("meta_data", []) if isinstance(aggregated, dict) else []
        
        if not dynamic_meta:
            logger.info(f"No B2B group found for price list: {price_list_name}")
            return
        
        # Sadece meta_data güncellemesi için payload
        wc_payload = {"meta_data": dynamic_meta}
        
        consumer_key = get_consumer_key()
        consumer_secret = get_consumer_secret()
        
        if not consumer_key or not consumer_secret:
            logger.error(f"Consumer key veya secret bulunamadı - Item: {item_code}")
            return
        
        # WooCommerce'e gönder
        logger.info(f"WooCommerce'e meta_data gönderiliyor - Item: {item_code}, WC ID: {existing_wc_id}")
        send_to_woocommerce(wc_payload, consumer_key, consumer_secret, item_code, existing_wc_id)
        logger.info(f"sync_item_price_to_woocommerce tamamlandı - Item: {item_code}")
    except Exception as e:
        logger.error(f"sync_item_price_to_woocommerce hatası - Item: {item_code}, Error: {str(e)}\n{frappe.get_traceback()}")
        frappe.log_error(
            title="Item Price Sync Error",
            message=f"Item: {item_code}, Price List: {price_list_name}\n{frappe.get_traceback()}"
        )


def sync_item_to_woocommerce(item_code: str):
    """Item'ı WooCommerce'e senkronize eder (queue'da çalışır)"""
    logger = frappe.logger("culinary_portal", allow_site=True)
    try:
        logger.info(f"sync_item_to_woocommerce başladı - Item: {item_code}")
        frappe.set_user("Administrator")
        
        # Item'ı yükle
        doc = frappe.get_doc("Item", item_code)
        logger.info(f"Item yüklendi: {item_code}")
        
        # Sync tarafından oluşturulan/güncellenen kayıtları atla
        if getattr(doc.flags, "created_by_sync", None):
            logger.info(f"Item {item_code} created_by_sync flag'i var, atlanıyor")
            return
        
        payload = doc.as_dict()
        consumer_key = get_consumer_key()
        consumer_secret = get_consumer_secret()
        
        if not consumer_key or not consumer_secret:
            logger.error(f"Consumer key veya secret bulunamadı - Item: {item_code}")
            return
        
        # Item değişikliği ise - normal akış
        base_url = get_base_url()
        logger.info(f"base_url: {base_url}")

        # Item'ın WooCommerce ID'sini kontrol et
        existing_wc_id = None
        try:
            existing_wc_id = frappe.db.get_value("Item", {"name": item_code}, "custom_woocommerce_id")
            logger.info(f"Existing WC ID: {existing_wc_id}")
        except Exception as e:
            logger.error(f"WC ID alınırken hata: {e}")
            existing_wc_id = None

        # Item Group'tan kategori ID'sini al
        category_id = None
        try:
            item_group_name = payload.get("item_group")
            if item_group_name:
                category_id = frappe.db.get_value(
                    "Item Group", {"name": item_group_name}, "custom_woocommerce_category_id"
                )
                logger.info(f"Item Group '{item_group_name}' -> category_id: {category_id}")
        except Exception as e:
            logger.error(f"Category ID alınırken hata: {e}")
            category_id = None

        # Ürüne bağlı birleşik meta_data (tek obje) al - tüm B2B grupları
        aggregated = collect_customer_b2bking_groups_for_item(item_code)
        dynamic_meta = aggregated.get("meta_data", []) if isinstance(aggregated, dict) else []
        logger.info(f"Meta data sayısı: {len(dynamic_meta)}")

        # Standard Selling fiyat kontrolü
        standard_price = _get_standard_selling_price(item_code)
        logger.info(f"standard_price: {standard_price}")
        
        # Status belirleme: disabled durumuna göre
        if payload.get("disabled", 0) == 1:
            status_value = "draft"
            logger.info("Item disabled, status = draft")
        else:
            status_value = "publish"
            logger.info("Item enabled, status = publish")
        
        # Fiyat kontrolü - eğer fiyat yoksa draft yap
        try:
            std_price_num = float(standard_price) if standard_price is not None else 0.0
        except Exception:
            std_price_num = 0.0
        if standard_price is None or std_price_num == 0.0:
            status_value = "draft"
            logger.info("Fiyat yok, status = draft")

        # WooCommerce formatına dönüştür
        wc_payload = map_item_to_woocommerce(
            doc,
            payload,
            base_url,
            category_id,
            dynamic_meta,
            status_value=status_value,
            regular_price_override=str(standard_price) if standard_price is not None else None,
        )
        logger.info(f"WC payload hazırlandı, keys: {list(wc_payload.keys())}")

        # WooCommerce'e gönder
        logger.info(f"WooCommerce'e gönderiliyor - Item: {item_code}, WC ID: {existing_wc_id}")
        send_to_woocommerce(wc_payload, consumer_key, consumer_secret, item_code, existing_wc_id)
        logger.info(f"sync_item_to_woocommerce tamamlandı - Item: {item_code}")
    except Exception as e:
        logger.error(f"sync_item_to_woocommerce hatası - Item: {item_code}, Error: {str(e)}\n{frappe.get_traceback()}")
        frappe.log_error(
            title="Item Sync Error",
            message=f"Item: {item_code}\n{frappe.get_traceback()}"
        )


def handle_item_saved(doc, method=None):
    print("\n\n\n DEBUG:0 handle_item_saved", doc)
    if doc.doctype=="Item Price":
        print("\n\n\n DEBUG:0 handle_item_saved Item Price", doc.as_dict())
    
    # Aynı istek içinde tekrar çalışmayı engelle
    if getattr(doc.flags, "culinary_wc_sync_ran", False):
        return
    doc.flags.culinary_wc_sync_ran = True

    # Sync tarafından oluşturulan/güncellenen kayıtları atla
    if getattr(doc.flags, "created_by_sync", None):
        return

    # Item Price değişikliği ise - queue'ya al
    if doc.doctype == "Item Price":
        item_code = doc.item_code
        price_list_name = doc.price_list
        
        print(f"DEBUG: Item Price queue'ya ekleniyor - Item: {item_code}, Price List: {price_list_name}")
        frappe.enqueue(
            "culinary_portal.custom_hooks.create_item.sync_item_price_to_woocommerce",
            item_code=item_code,
            price_list_name=price_list_name,
            queue="default",
            timeout=300,
            job_id=f"sync_item_price_{item_code}_{price_list_name}",
            deduplicate=True,
            enqueue_after_commit=True
        )
        return

    # Item değişikliği ise - queue'ya al
    item_code = doc.name if hasattr(doc, 'name') else doc.item_code
    
    print(f"DEBUG: Item queue'ya ekleniyor - Item: {item_code}")
    frappe.enqueue(
        "culinary_portal.custom_hooks.create_item.sync_item_to_woocommerce",
        item_code=item_code,
        queue="default",
        timeout=300,
        job_id=f"sync_item_{item_code}",
        deduplicate=True,
        enqueue_after_commit=True
    )
    
    frappe.msgprint(frappe._("Item sync işlemi kuyruğa eklendi"))



def map_item_to_woocommerce(doc, item_data, base_url, category_id: int | None, meta_data: list[dict], status_value: str = "publish", regular_price_override: str | None = None):
    """ERPNext Item verisini Portal formatına dönüştürür"""
    print("\n\n\n DEBUG:1 DOC NAME", doc)
    
    # UOM bilgilerini meta_data'ya ekle
    uom_meta = []
    
    # product_uom - stock_uom değerini gönder
    stock_uom = item_data.get("stock_uom") or (doc.stock_uom if hasattr(doc, 'stock_uom') else None)
    if stock_uom:
        uom_meta.append({"key": "product_uom", "value": stock_uom})
    
    # convertion_uom ve convertion_rate - UOM Conversion Detail'den al
    if doc.doctype == "Item":
        # Önce doc'tan dene
        uoms_list = None
        if hasattr(doc, 'uoms') and doc.uoms:
            uoms_list = doc.uoms
        # Doc'ta yoksa item_data'dan dene
        elif item_data.get("uoms"):
            uoms_list = item_data.get("uoms")
        
        if uoms_list and len(uoms_list) > 0:
            first_uom = uoms_list[0]
            # Dict veya object olabilir
            uom_value = first_uom.get("uom") if isinstance(first_uom, dict) else (first_uom.uom if hasattr(first_uom, 'uom') else None)
            conversion_factor = first_uom.get("conversion_factor") if isinstance(first_uom, dict) else (first_uom.conversion_factor if hasattr(first_uom, 'conversion_factor') else None)
            
            if uom_value:
                uom_meta.append({"key": "convertion_uom", "value": uom_value})
            if conversion_factor is not None:
                uom_meta.append({"key": "convertion_rate", "value": str(conversion_factor)})
    
    # Mevcut meta_data ile birleştir
    if uom_meta:
        meta_data = (meta_data or []) + uom_meta
    
    image_path = item_data.get("image", "") or ""
    images = []  # Default boş array
    if image_path:
        # Private files kontrolü - WooCommerce erişemez
        if "/private/" in image_path:
            print(f"⚠️ Private file atlandı (WooCommerce'deki eski görsel silinecek): {image_path}")
            images = []  # Boş array göndererek WooCommerce'deki görseli sil
        else:
            # Public file - WooCommerce'e gönder
            images = [
                {
                    "src": f"{base_url}{image_path}",
                    "name": item_data.get("item_name", ""),
                    "alt": item_data.get("item_name", ""),
                }
            ]

    # Categories başlangıcı - Item Group categories'ini ekle
    categories = []
    
    # 1. Vendor ana kategorisi - dinamik olarak al
    vendor_cat_id = get_vendor_category_id()
    if not vendor_cat_id:
        # Vendor kategori ID yoksa işlemi durdur
        frappe.throw(frappe._("Lütfen 'Vendor' ürün grubunu oluşturun ve WooCommerce kategori ID'sini tanımlayın"))
    
    categories.append({"id": vendor_cat_id})
    print(f"DEBUG: Added Vendor category ID: {vendor_cat_id}")
    
    # 2. Item Group kategori ID'sini ekle
    if category_id and str(category_id).isdigit():
        categories.append({"id": int(category_id)})
        print(f"DEBUG: Added Item Group category ID: {category_id}")

    # regular_price tercihi: override > item.standard_rate
    regular_price_value = (
        regular_price_override
        if regular_price_override is not None
        else str(item_data.get("standard_rate", "0.0"))
    )
    
    if doc.doctype == "Item":
        # Supplier categories'ini de ekle
        supplier_items = []
        if hasattr(doc, 'supplier_items') and doc.supplier_items:
            # Supplier ID'lerini önce topla
            supplier_names = [item.supplier for item in doc.supplier_items if item.supplier]
            
            # Supplier bilgilerini tek sorguda çek
            supplier_data = {}
            if supplier_names:
                supplier_categories = frappe.db.get_list(
                    "Supplier",
                    filters={"name": ["in", supplier_names]},
                    fields=["name", "custom_woocommerce_category_id","custom_woocommerce_vendor_id"],
                    limit_page_length=0
                )
                supplier_data = {s.name: s.custom_woocommerce_category_id for s in supplier_categories if s.custom_woocommerce_category_id}
                print(f"\n\n\n DEBUG:1 supplier_data", supplier_data)
            
            # Supplier categories'ini categories'e ekle
            for supplier_name, supplier_cat_id in supplier_data.items():
                if supplier_cat_id and str(supplier_cat_id).isdigit():
                    supplier_cat_int = int(supplier_cat_id)
                    # Aynı kategori zaten ekli mi kontrol et
                    existing_ids = [c.get("id") for c in categories]
                    if supplier_cat_int not in existing_ids:
                        categories.append({"id": supplier_cat_int, "parent": vendor_cat_id})
                        print(f"DEBUG: Added Supplier category ID: {supplier_cat_int} for supplier: {supplier_name}")
        
        print(f"\n\n\n DEBUG:1 Final categories", categories)
        
        wc_data = {
            "name": item_data.get("item_name", ""),
            "slug": item_data.get("item_code", ""),
            "type": "simple",
            "sku": item_data.get("item_code", ""),       
            "description": item_data.get("description", ""),
            "short_description":item_data.get("custom_short_description",""),
            "manage_stock": False,
            "stock_status": "instock",
            "status": status_value,
            "categories": categories,
            "images": images,
            "meta_data": meta_data or [],
        }
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
        
        if not hasattr(item_doc, 'supplier_items') or not item_doc.supplier_items:
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
        
        dokan_payload = {
            "post_author": str(vendor_id)
        }
        
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
    logger = frappe.logger("culinary_portal", allow_site=True)
    try:
        url = f"{get_wo_url()}/wp-json/wc/v3/products"
        logger.info(f"WooCommerce URL: {url}, Item: {item_code}, Existing WC ID: {existing_wc_id}")

        # ID varsa güncelle, yoksa yeni oluştur
        if existing_wc_id:
            request_url = f"{url}/{existing_wc_id}"
            logger.info(f"PUT isteği gönderiliyor: {request_url}")
            response = requests.put(
                request_url,
                auth=(consumer_key, consumer_secret),
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            logger.info(f"PUT response status: {response.status_code}")
            wc_product_id = existing_wc_id
        else:
            logger.info(f"POST isteği gönderiliyor: {url}")
            response = requests.post(
                url,
                auth=(consumer_key, consumer_secret),
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            logger.info(f"POST response status: {response.status_code}")
            wc_product_id = None

        if response.status_code in (200, 201):
            response_data = response.json()
            wc_product_id = response_data.get("id")
            logger.info(f"✅ WooCommerce başarılı - Product ID: {wc_product_id}, Item: {item_code}")
            
            # Eğer yeni oluşturulduysa, Item'a WooCommerce ID'yi kaydet
            if wc_product_id and not existing_wc_id:
                try:
                    frappe.db.set_value("Item", item_code, "custom_woocommerce_id", wc_product_id)
                    frappe.db.commit()
                    logger.info(f"✅ Portal ID ({wc_product_id}) Item'a kaydedildi")
                except Exception as e:
                    logger.error(f"Portal ID kaydedilirken hata: {e}")
                    frappe.log_error(
                        title="Item Portal ID Update Error",
                        message=f"Item: {item_code}, WC ID: {wc_product_id}, Error: {str(e)}"
                    )
            
            # Dokan API'sine post_author güncelleme isteği gönder 
            # (sadece tam Item kaydı için, meta_data-only güncellemelerde çalıştırma)
            is_meta_only_update = len(payload) == 1 and "meta_data" in payload
            if wc_product_id and not is_meta_only_update:
                logger.info(f"Dokan post_author güncelleniyor - Product ID: {wc_product_id}")
                update_dokan_post_author(item_code, wc_product_id)
        else:
            error_msg = f"Status: {response.status_code}\nResponse: {response.text}\nItem: {item_code}\nURL: {url}"
            logger.error(f"❌ WooCommerce API hatası: {error_msg}")
            frappe.log_error(
                title="Portal API Error",
                message=error_msg,
            )

    except Exception as e:
        error_msg = f"Item: {item_code}\n{frappe.get_traceback()}"
        logger.error(f"❌ send_to_woocommerce hatası: {error_msg}")
        frappe.log_error(
            title="Portal Send Error",
            message=error_msg,
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
            return {
                "status": "warning",
                "message": "Senkronize edilecek ürün bulunamadı"
            }
        
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
                existing_wc_id = frappe.db.get_value("Item", {"name": payload.get("item_code")}, "custom_woocommerce_id")
                
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
                frappe.log_error(
                    title=f"Item Sync Error - {item_dict.name}",
                    message=frappe.get_traceback()
                )
        
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
            "error_count": error_count
        }
        
    except Exception as e:
        frappe.log_error(
            title="Bulk Item Sync Error",
            message=frappe.get_traceback()
        )
        return {
            "status": "error",
            "message": f"Toplu senkronizasyon hatası: {str(e)}"
        }


