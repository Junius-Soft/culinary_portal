import frappe
import requests
from typing import Optional

from culinary_portal.custom_hooks.create_item import (
    get_base_url,
    get_consumer_key,
    get_consumer_secret,
    get_wo_url,
)


def _build_image_src(image_path: Optional[str]) -> str:
    """Item Group.image alanından public URL üretir; yoksa boş string döner."""
    if not image_path:
        return ""
    base_url = get_base_url()
    return f"{base_url}{image_path}"


def _post_wc_category(name: str, image_src: str) -> Optional[int]:
    """WooCommerce kategori oluşturur ve id döner; hata halinde None."""
    try:
        url = `get_wo_url()"/wp-json/wc/v3/products/categories"`
        payload = {
            "name": name or "",
            "image": {"src": image_src or ""},
        }
        print("\n\n\n DEBUG:1 payload", payload)
        resp = requests.post(
            url,
            auth=(get_consumer_key(), get_consumer_secret()),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            return data.get("id") if isinstance(data, dict) else None
        frappe.log_error(
            title="WooCommerce Category POST Error",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}.",
        )
    except Exception:
        frappe.log_error(
            title="WooCommerce Category POST Exception",
            message=frappe.get_traceback(),
        )
    return None


def _update_wc_category(category_id: int, name: str, image_src: str) -> bool:
    """Mevcut WooCommerce kategoriyi günceller; başarılı olursa True döner."""
    try:
        url =`get_wo_url()f"/wp-json/wc/v3/products/categories/{category_id}"` 
        payload = {
            "name": name or "",
            "image": {"src": image_src or ""},
            "slug": name.lower().replace(" ", "-"),
        }
        print(f"\n\n\n DEBUG:2 UPDATE payload for category {category_id}", payload)
        resp = requests.put(
            url,
            auth=(get_consumer_key(), get_consumer_secret()),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        if resp.status_code in (200, 201):
            print(f"\n\n\n DEBUG:3 UPDATE successful for category {category_id}")
            return True
        frappe.log_error(
            title="WooCommerce Category UPDATE Error",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="WooCommerce Category UPDATE Exception",
            message=frappe.get_traceback(),
        )
    return False


def _delete_wc_category(category_id: int, force_delete: bool = True) -> bool:
    """WooCommerce kategorisini siler; başarılı olursa True döner."""
    try:
        url = `get_wo_url()f"/wp-json/wc/v3/products/categories/{category_id}"` 
        params = {"force": force_delete} if force_delete else {}
        
        print(f"\n\n\n DEBUG:4 DELETE request for category {category_id}")
        resp = requests.delete(
            url,
            auth=(get_consumer_key(), get_consumer_secret()),
            params=params,
            timeout=40,
        )
        if resp.status_code in (200, 204):
            print(f"\n\n\n DEBUG:5 DELETE successful for category {category_id}")
            return True
        frappe.log_error(
            title="WooCommerce Category DELETE Error",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="WooCommerce Category DELETE Exception",
            message=frappe.get_traceback(),
        )
    return False


def handle_item_group_after_insert(doc, method=None, old=None, new=None, merge=False):
    print("\n\n\n DEBUG:0 handle_item_group_after_insert", doc)
    """Item Group oluşturulduğunda WooCommerce'te kategori oluşturur veya günceller."""
    print("\n\n\n DEBUG:0 handle_item_group_after_insert", doc)
    try:
        # Aynı istek içinde tekrar çalışmayı engelle
        if getattr(doc.flags, "culinary_wc_cat_sync_ran", False):
            return
        doc.flags.culinary_wc_cat_sync_ran = True

        # Mevcut WooCommerce kategori ID'sini kontrol et
        existing_wc_id = getattr(doc, "custom_woocommerce_category_id", None)
        print("\n\n\n DEBUG:1 existing_wc_id", existing_wc_id)
        
        name = getattr(doc, "item_group_name", None) or getattr(doc, "name", None) or ""
        image_src = _build_image_src(getattr(doc, "image", None))

        if existing_wc_id:
            # Mevcut kategoriyi güncelle
            print(f"\n\n\n DEBUG:4 Updating existing category {existing_wc_id}")
            update_success = _update_wc_category(
                category_id=existing_wc_id,
                name=name,
                image_src=image_src
            )
            if not update_success:
                frappe.log_error(
                    title="WooCommerce Category Update Failed",
                    message=f"Failed to update category {existing_wc_id} for Item Group {doc.name}",
                )
        else:
            # Yeni kategori oluştur
            print("\n\n\n DEBUG:5 Creating new category")
            wc_category_id = _post_wc_category(name=name, image_src=image_src)
            print("\n\n\n DEBUG:1 wc_category_id", wc_category_id)
            if wc_category_id:
                try:
                    frappe.db.set_value(
                        "Item Group", doc.name, "custom_woocommerce_category_id", wc_category_id
                    )
                    frappe.db.commit()
                except Exception:
                    frappe.log_error(
                        title="Item Group WooCommerce Category ID Update Error",
                        message=frappe.get_traceback(),
                    )
    except Exception:
        frappe.log_error(
            title="Item Group WooCommerce Category Sync Error",
            message=frappe.get_traceback(),
        )


def handle_item_group_on_trash(doc, method=None):
    """Item Group silindiğinde WooCommerce'teki karşılık gelen kategoriyi de siler."""
    print("\n\n\n DEBUG:6 handle_item_group_on_trash", doc)
    try:
        # WooCommerce kategori ID'sini kontrol et
        existing_wc_id = getattr(doc, "custom_woocommerce_category_id", None)
        print("\n\n\n DEBUG:7 existing_wc_id for delete", existing_wc_id)
        
        if existing_wc_id:
            # WooCommerce'de kategoriyi sil
            print(f"\n\n\n DEBUG:8 Deleting WooCommerce category {existing_wc_id}")
            delete_success = _delete_wc_category(category_id=existing_wc_id)
            
            if not delete_success:
                frappe.log_error(
                    title="WooCommerce Category Delete Failed",
                    message=f"Failed to delete category {existing_wc_id} for Item Group {doc.name}",
                )
            else:
                print(f"\n\n\n DEBUG:9 Successfully deleted WooCommerce category {existing_wc_id}")
        else:
            print("\n\n\n DEBUG:10 No WooCommerce category ID found, skipping delete")
            
    except Exception:
        frappe.log_error(
            title="Item Group WooCommerce Category Delete Sync Error",
            message=frappe.get_traceback(),
        )
