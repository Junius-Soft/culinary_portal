import frappe
import requests
from frappe.utils import get_url


def get_wo_url():
    """WooCommerce URL'ini site config'den veya default URL'den alır"""
    site_conf = getattr(frappe.local, "conf", {}) or {}
    return site_conf.get("woocommerce_url") or get_url()


def get_consumer_key():
    """WooCommerce API Consumer Key'i döndürür"""
    woocommerce_server = frappe.get_value("WooCommerce Server", "www.temayolu.com", "api_consumer_key")
    return woocommerce_server or ""


def get_consumer_secret():
    """WooCommerce API Consumer Secret'ı döndürür"""
    woocommerce_server = frappe.get_value("WooCommerce Server", "www.temayolu.com", "api_consumer_secret")
    return woocommerce_server or ""


def handle_item_deleted(doc, method=None):
    """Item silindiğinde WooCommerce'den de siler"""
    print(f"\n\n\n DEBUG: Item siliniyor - {doc.name}")
    
    # Sync tarafından oluşturulan/güncellenen kayıtları atla
    if getattr(doc.flags, "created_by_sync", None):
        return
    
    # WooCommerce ID'yi kontrol et
    wc_id = doc.get("custom_woocommerce_id")
    
    if not wc_id:
        print(f"DEBUG: Item '{doc.name}' için WooCommerce ID bulunamadı, silme işlemi atlanıyor")
        return
    
    # WooCommerce'den sil
    try:
        delete_from_woocommerce(wc_id, doc.name)
    except Exception as e:
        frappe.log_error(
            title="Item Delete from WooCommerce Error",
            message=f"Item: {doc.name}, WC ID: {wc_id}, Error: {str(e)}\n\n{frappe.get_traceback()}"
        )
        # Hata olsa bile ERPNext'ten silinmesine izin ver
        print(f"DEBUG: WooCommerce'den silme hatası: {str(e)}")


def delete_from_woocommerce(wc_product_id, item_code):
    """WooCommerce API'sinden ürünü siler (force delete)"""
    try:
        consumer_key = get_consumer_key()
        consumer_secret = get_consumer_secret()
        
        if not consumer_key or not consumer_secret:
            print("DEBUG: WooCommerce API credentials bulunamadı")
            return
        
        url = f"{get_wo_url()}/wp-json/wc/v3/products/{wc_product_id}"
        
        # force=true parametresi ile kalıcı silme
        response = requests.delete(
            url,
            auth=(consumer_key, consumer_secret),
            params={"force": "true"},
            headers={"Content-Type": "application/json"},
        )
        
        if response.status_code == 200:
            print(f"✅ WooCommerce ürün silindi - Item: {item_code}, WC ID: {wc_product_id}")
            frappe.msgprint(frappe._("Product successfully deleted from WooCommerce"), alert=True)
        elif response.status_code == 404:
            print(f"⚠️ WooCommerce'de ürün bulunamadı - Item: {item_code}, WC ID: {wc_product_id}")
        else:
            error_msg = f"Status: {response.status_code}\nResponse: {response.text}"
            print(f"❌ WooCommerce silme hatası - {error_msg}")
            frappe.log_error(
                title="WooCommerce Product Delete Error",
                message=f"Item: {item_code}, WC ID: {wc_product_id}\n{error_msg}"
            )
            
    except Exception as e:
        frappe.log_error(
            title="WooCommerce Delete Error",
            message=f"Item: {item_code}, WC ID: {wc_product_id}\n{frappe.get_traceback()}"
        )
        raise


@frappe.whitelist()
def bulk_delete_items_from_woocommerce(item_codes):
    """Toplu ürün silme - WooCommerce'den siler (ERPNext'ten silmez)"""
    try:
        if isinstance(item_codes, str):
            import json
            item_codes = json.loads(item_codes)
        
        if not item_codes:
            return {
                "status": "warning",
                "message": "Silinecek ürün bulunamadı"
            }
        
        success_count = 0
        error_count = 0
        error_items = []
        
        for item_code in item_codes:
            try:
                wc_id = frappe.db.get_value("Item", item_code, "custom_woocommerce_id")
                
                if not wc_id:
                    error_items.append(f"{item_code} (WooCommerce ID yok)")
                    error_count += 1
                    continue
                
                delete_from_woocommerce(wc_id, item_code)
                
                # Başarılı ise Item'daki WooCommerce ID'yi temizle
                frappe.db.set_value("Item", item_code, "custom_woocommerce_id", None)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                error_items.append(f"{item_code} ({str(e)})")
        
        frappe.db.commit()
        
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
            title="Bulk Delete Error",
            message=frappe.get_traceback()
        )
        return {
            "status": "error",
            "message": f"Toplu silme hatası: {str(e)}"
        }

