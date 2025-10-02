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


def get_consumer_key():
    site_conf = getattr(frappe.local, "conf", {}) or {}
    return site_conf.get("consumer_key") or ""


def get_consumer_secret():
    site_conf = getattr(frappe.local, "conf", {}) or {}
    return site_conf.get("consumer_secret") or ""


def get_wc_category_id(category_name: str, consumer_key: str, consumer_secret: str) -> int | None:
    """WooCommerce'de kategori adını arayıp id'sini döndürür; yoksa None."""
    if not category_name:
        return None
    try:
        url = "https://staging.erpsfer.com/culinary/wp-json/wc/v3/products/categories"
        resp = requests.get(
            url,
            auth=(consumer_key, consumer_secret),
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
    url = "https://staging.erpsfer.com/culinary/wp-json/wc/v3/customers"
    try:
        resp = requests.get(
            url,
            auth=(consumer_key, consumer_secret),
            params={"email": email},
            headers={"Content-Type": "application/json"},
        )
        data = resp.json()
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
        frappe.msgprint("Ürünün fiyatı yok", alert=True)

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
    url = "https://staging.erpsfer.com/culinary/wp-json/wc/v3/products"
    print("\n\n\n DEBUG:0 base_url", base_url)

    # Kategori id'yi al
    category_id = get_wc_category_id(payload.get("item_group", ""), consumer_key, consumer_secret)

    # Ürüne bağlı birleşik meta_data (tek obje) al
    aggregated = collect_customer_b2bking_groups_for_item(payload.get("item_code"))
    dynamic_meta = aggregated.get("meta_data", []) if isinstance(aggregated, dict) else []

    # Standard Selling fiyat kontrolü
    standard_price = _get_standard_selling_price(payload.get("item_code"))
    print("\n\n\n DEBUG:1 standard_price", standard_price)
    status_value = "publish"
    # 0.0 veya None ise draft yap ve uyarı ver
    try:
        std_price_num = float(standard_price) if standard_price is not None else 0.0
    except Exception:
        std_price_num = 0.0
    if standard_price is None or std_price_num == 0.0:
        frappe.msgprint("Ürün fiyatı tanımlanmadı Ürün Draft olark eklenecktir", alert=True)
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

    # WooCommerce'e gönder ve item_code'u da geç
    send_to_woocommerce(wc_payload, consumer_key, consumer_secret, payload.get("item_code"))


def map_item_to_woocommerce(doc,item_data, base_url, category_id: int | None, meta_data: list[dict], status_value: str = "publish", regular_price_override: str | None = None):
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

    categories = []
    if category_id:
        categories = [{"id": category_id}]

    # regular_price tercihi: override > item.standard_rate
    regular_price_value = (
        regular_price_override
        if regular_price_override is not None
        else str(item_data.get("standard_rate", "0.0"))
    )
    
    if doc.doctype=="Item":
        wc_data = {
            "name": item_data.get("item_name", ""),
            "slug": item_data.get("item_code", ""),
            "type": "simple",
            "sku": item_data.get("item_code", ""),       
            "description": item_data.get("description", ""),
            "manage_stock": True,
            "stock_quantity": 100,
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


def send_to_woocommerce(payload, consumer_key, consumer_secret, item_code):
    """WooCommerce API'sine veri gönderir ve dönen ID'yi Item'a kaydeder"""
    try:
        url = "https://staging.erpsfer.com/culinary/wp-json/wc/v3/products"

        # SKU ile ürün arama: query param kullanın
        item_check_response = requests.get(
            url,
            auth=(consumer_key, consumer_secret),
            params={"sku": payload.get("sku")},
            headers={"Content-Type": "application/json"},
        )
        data = item_check_response.json()

        product_id = None
        if isinstance(data, list) and data:
            product_id = data[0].get("id")
        elif isinstance(data, dict):
            product_id = data.get("id")
        if item_check_response.status_code == 200 and product_id:
            response = requests.put(
                f"{url}/{product_id}",
                auth=(consumer_key, consumer_secret),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        else:
            response = requests.post(
                url,
                auth=(consumer_key, consumer_secret),
                json=payload,
                headers={"Content-Type": "application/json"},
            )

        if response.status_code in (200, 201):
            response_data = response.json()
            wc_product_id = response_data.get("id")
            
            if wc_product_id:
                # Item doctype'ındaki custom_woocommerce_id alanını güncelle
                try:
                    frappe.db.set_value("Item", item_code, "custom_woocommerce_id", wc_product_id)
                    frappe.db.commit()
                    print(f"✅ WooCommerce ID ({wc_product_id}) Item'a kaydedildi")
                except Exception as e:
                    frappe.log_error(
                        title="Item WooCommerce ID Update Error",
                        message=f"Item: {item_code}, WC ID: {wc_product_id}, Error: {str(e)}"
                    )
            
            frappe.msgprint("Item WooCommerce'e başarıyla senkronize edildi")
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


