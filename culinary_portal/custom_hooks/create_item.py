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

# def get_consumer_key():
#     woocommerce_server = frappe.get_value("WooCommerce Server", "www.temayolu.com", "api_consumer_key")

#     return woocommerce_server or ""


# def get_consumer_secret():
#     woocommerce_server = frappe.get_value("WooCommerce Server", "www.temayolu.com", "api_consumer_secret")
#     return woocommerce_server or ""
# Debug prints removed for security

def get_wc_category_id(category_name: str) -> int | None:
    """WooCommerce'de kategori adını arayıp id'sini döndürür; yoksa None."""
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
    """Verilen e‑posta için WooCommerce customers API'den kullanıcının id ve meta_data'sını döndürür."""
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
        print("\n\n\n\ DEBUGG---111---",resp)
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

    payload = doc.as_dict()
    base_url = get_base_url()
    consumer_key = get_consumer_key()
    consumer_secret = get_consumer_secret()
    url = f"{get_wo_url()}/wp-json/wc/v3/products"
    print("\n\n\n DEBUG:0 base_url", base_url)

    # Item'ın WooCommerce ID'sini kontrol et
    existing_wc_id = None
    try:
        existing_wc_id = frappe.db.get_value("Item", {"name": payload.get("item_code")}, "custom_woocommerce_id")
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

    # Ürüne bağlı birleşik meta_data (tek obje) al
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
    
    # Fiyat kontrolü - eğer fiyat yoksa draft yap
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
        regular_price_override=str(standard_price) if standard_price is not None else None,
    )

    # WooCommerce'e gönder ve item_code ile existing_wc_id'yi geç
    send_to_woocommerce(wc_payload, consumer_key, consumer_secret, payload.get("item_code"), existing_wc_id)


def map_item_to_woocommerce(doc, item_data, base_url, category_id: int | None, meta_data: list[dict], status_value: str = "publish", regular_price_override: str | None = None):
    """ERPNext Item verisini WooCommerce formatına dönüştürür"""
    print("\n\n\n DEBUG:1 DOC NAME", doc)
    image_path = item_data.get("image", "") or ""
    images = []
    if image_path:
        images = [
            {
                "src": f"{base_url}{image_path}",
                "name": item_data.get("item_name", ""),
                "alt": item_data.get("item_name", ""),
            }
        ]

    # Categories başlangıcı - Item Group categories'ini ekle
    categories = []
    
    # 1. Item Group kategori ID'sini ekle (ana kategori olarak)
    if category_id and str(category_id).isdigit():
        categories.append({"id": int(category_id)})
        print(f"DEBUG: Added Item Group category ID: {category_id}")
    
    # 2. Ana kategori (303) - her zaman eklenir
    categories.append({"id": 303})
    print(f"DEBUG: Categories after Item Group: {categories}")

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
                        categories.append({"id": supplier_cat_int, "parent": 303})
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


def send_to_woocommerce(payload, consumer_key, consumer_secret, item_code, existing_wc_id=None):
    """WooCommerce API'sine veri gönderir ve dönen ID'yi Item'a kaydeder"""
    try:
        url = f"{get_wo_url()}/wp-json/wc/v3/products"
        dokanurl=f"{get_wo_url()}/wp-json/dokan/v1/products"

        # ID varsa güncelle, yoksa yeni oluştur
        if existing_wc_id:
            response = requests.put(
                f"{url}/{existing_wc_id}",
                auth=(consumer_key, consumer_secret),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            print(f"🔄 WooCommerce ürün güncellendi - ID: {existing_wc_id}")
        else:
            response = requests.post(
                url,
                auth=(consumer_key, consumer_secret),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            print("➕ Yeni WooCommerce ürün oluşturuluyor",response)

        if response.status_code in (200, 201):
            response_data = response.json()
            wc_product_id = response_data.get("id")
            
            # Eğer yeni oluşturulduysa, Item'a WooCommerce ID'yi kaydet
            if wc_product_id and not existing_wc_id:
                try:
                    frappe.db.set_value("Item", item_code, "custom_woocommerce_id", wc_product_id)
                    frappe.db.commit()
                    print(f"✅ WooCommerce ID ({wc_product_id}) Item'a kaydedildi")
                except Exception as e:
                    frappe.log_error(
                        title="Item WooCommerce ID Update Error",
                        message=f"Item: {item_code}, WC ID: {wc_product_id}, Error: {str(e)}"
                    )
            
            frappe.msgprint(frappe._("Item successfully synchronized to WooCommerce"))
            print("\n\n\n DEBUG:2 wc_product_id", payload)
        else:
            frappe.log_error(
                title="WooCommerce API Error",
                message=f"Status: {response.status_code}\nResponse: {response.text}",
            )

    except Exception as e:
        frappe.log_error(
            title="WooCommerce Send Error",
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
    """Tüm Item'ları WooCommerce'e senkronize eder"""
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


