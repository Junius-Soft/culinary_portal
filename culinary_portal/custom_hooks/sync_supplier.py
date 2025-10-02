import frappe
import requests
from typing import Optional

from culinary_portal.custom_hooks.create_item import (
    get_base_url,
    get_consumer_key,
    get_consumer_secret,
)


def _build_image_src(image_path: Optional[str]) -> str:
    """Supplier.image alanından public URL üretir; yoksa boş string döner."""
    if not image_path:
        return ""
    base_url = get_base_url()
    return f"{base_url}{image_path}"


def _post_wc_category(name: str,  slug: Optional[str] = None, parent_id: Optional[int] = None) -> Optional[int]:
    """WooCommerce kategori oluşturur ve id döner; hata halinde None."""
    try:
        url = "https://staging.erpsfer.com/culinary/wp-json/wc/v3/products/categories"
        payload: dict = {
            "name": name or "",
            
        }
        if slug:
            payload["slug"] = slug
        if parent_id:
            payload["parent"] = parent_id
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
            title="WooCommerce Category POST Error (Supplier)",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="WooCommerce Category POST Exception (Supplier)",
            message=frappe.get_traceback(),
        )
    return None


def _update_wc_category(category_id: int, name: str, image_src: str, slug: Optional[str] = None, parent_id: Optional[int] = None) -> bool:
    """Mevcut WooCommerce kategoriyi günceller; başarılı olursa True döner."""
    try:
        url = f"https://staging.erpsfer.com/culinary/wp-json/wc/v3/products/categories/{category_id}"
        payload: dict = {
            "name": name or "",
            "image": {"src": image_src or ""},
        }
        if slug:
            payload["slug"] = slug
        if parent_id:
            payload["parent"] = parent_id
        resp = requests.put(
            url,
            auth=(get_consumer_key(), get_consumer_secret()),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        if resp.status_code in (200, 201):
            return True
        frappe.log_error(
            title="WooCommerce Category UPDATE Error (Supplier)",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="WooCommerce Category UPDATE Exception (Supplier)",
            message=frappe.get_traceback(),
        )
    return False


def _delete_wc_category(category_id: int, force_delete: bool = True) -> bool:
    """WooCommerce kategorisini siler; başarılı olursa True döner."""
    try:
        url = f"https://staging.erpsfer.com/culinary/wp-json/wc/v3/products/categories/{category_id}"
        params = {"force": force_delete} if force_delete else {}
        resp = requests.delete(
            url,
            auth=(get_consumer_key(), get_consumer_secret()),
            params=params,
            timeout=40,
        )
        if resp.status_code in (200, 204):
            return True
        frappe.log_error(
            title="WooCommerce Category DELETE Error (Supplier)",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="WooCommerce Category DELETE Exception (Supplier)",
            message=frappe.get_traceback(),
        )
    return False


def handle_supplier_sync(doc, method=None, old=None, new=None, merge: bool = False):
    """Supplier oluşturulduğunda/güncellendiğinde WooCommerce'te kategori oluşturur veya günceller."""
    try:
        if getattr(doc.flags, "culinary_wc_supplier_sync_ran", False):
            return
        doc.flags.culinary_wc_supplier_sync_ran = True

        existing_wc_id = getattr(doc, "custom_woocommerce_category_id", None)
        name = getattr(doc, "supplier_name", None) or getattr(doc, "name", None) or ""
        image_src = _build_image_src(getattr(doc, "image", None))
        slug = getattr(doc, "custom_woocommerce_slug", None) or (name.lower().replace(" ", "-") if name else None)
        parent_id = 303  # Varsayılan üst kategori

        if existing_wc_id:
            updated = _update_wc_category(
                category_id=existing_wc_id,
                name=name,
                image_src=image_src,
                slug=slug,
                parent_id=parent_id,
            )
            if not updated:
                frappe.log_error(
                    title="WooCommerce Supplier Category Update Failed",
                    message=f"Failed to update category {existing_wc_id} for Supplier {doc.name}",
                )
        else:
            wc_category_id = _post_wc_category(name=name,  parent_id=parent_id)
            if wc_category_id:
                try:
                    frappe.db.set_value("Supplier", doc.name, "custom_woocommerce_category_id", wc_category_id)
                    frappe.db.commit()
                except Exception:
                    frappe.log_error(
                        title="Supplier WooCommerce Category ID Update Error",
                        message=frappe.get_traceback(),
                    )
    except Exception:
        frappe.log_error(
            title="Supplier WooCommerce Category Sync Error",
            message=frappe.get_traceback(),
        )


def handle_supplier_on_trash(doc, method=None):
    """Supplier silindiğinde WooCommerce'teki karşılık gelen kategoriyi de siler."""
    try:
        existing_wc_id = getattr(doc, "custom_woocommerce_category_id", None)
        if existing_wc_id:
            deleted = _delete_wc_category(existing_wc_id)
            if not deleted:
                frappe.log_error(
                    title="WooCommerce Supplier Category Delete Failed",
                    message=f"Failed to delete category {existing_wc_id} for Supplier {doc.name}",
                )
    except Exception:
        frappe.log_error(
            title="Supplier WooCommerce Category Delete Sync Error",
            message=frappe.get_traceback(),
        )
