import frappe
import requests
from typing import Optional

from culinary_portal.custom_hooks.create_item import (
    get_base_url,
    get_consumer_key,
    get_consumer_secret,
    get_wo_url,
    get_wp_user,
    get_wp_app_key,
    get_vendor_category_id
)


def _build_image_src(image_path: Optional[str]) -> str:
    """Supplier.image alanından public URL üretir; yoksa boş string döner."""
    if not image_path:
        return ""
    base_url = get_base_url()
    return f"{base_url}{image_path}"


def _post_wc_category(name: str,  slug: Optional[str] = None, parent_id: Optional[int] = None) -> Optional[int]:
    """Portal kategori oluşturur ve id döner; hata halinde None."""
    print(f"\n\n\n DEBUG:55 name: {name}, slug: {slug}, parent_id: {parent_id}")
    try:
        
        url = f"{get_wo_url()}/wp-json/wc/v3/products/categories" 
        print(f"\n\n\n DEBUG:1 url:",url)
        payload: dict = {
            "name": name or "",
            
        }
        if slug:
            payload["slug"] = slug
        if parent_id:
            payload["parent"] = parent_id
        consumer_key = get_consumer_key()
        consumer_secret = get_consumer_secret()
        
        print(f"\n\n\n DEBUG: Auth - Key: {consumer_key[:15]}..., Secret: {consumer_secret[:15]}...")
        
        resp = requests.post(
            url,
            auth=(consumer_key, consumer_secret),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        print(f"\n\n\n DEBUG:66 resp status: {resp.status_code}")
        print(f"\n\n\n DEBUG:66 resp body: {resp.text}")
        if resp.status_code in (200, 201):
            data = resp.json()
            return data.get("id") if isinstance(data, dict) else None
        frappe.log_error(
            title="Portal Category POST Error (Supplier)",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="Portal Category POST Exception (Supplier)",
            message=frappe.get_traceback(),
        )
    return None


def _update_wc_category(category_id: int, name: str, image_src: str, slug: Optional[str] = None, parent_id: Optional[int] = None) -> bool:
    """Mevcut Portal kategoriyi günceller; başarılı olursa True döner."""
    try:
        url = f"{get_wo_url()}/wp-json/wc/v3/products/categories/{category_id}" 
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
            title="Portal Category UPDATE Error (Supplier)",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="Portal Category UPDATE Exception (Supplier)",
            message=frappe.get_traceback(),
        )
    return False


def _delete_wc_category(category_id: int, force_delete: bool = True) -> bool:
    """Portal kategorisini siler; başarılı olursa True döner."""
    try:
        url = f"{get_wo_url()}/wp-json/wc/v3/products/categories/{category_id}" 
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
            title="Portal Category DELETE Error (Supplier)",
            message=f"Status: {resp.status_code}\nResponse: {resp.text}",
        )
    except Exception:
        frappe.log_error(
            title="Portal Category DELETE Exception (Supplier)",
            message=frappe.get_traceback(),
        )
    return False


def handle_supplier_sync(doc, method=None, old=None, new=None, merge: bool = False):
    """Supplier oluşturulduğunda/güncellendiğinde Portal'te kategori oluşturur veya günceller."""
    try:
        if getattr(doc.flags, "culinary_wc_supplier_sync_ran", False):
            return
        doc.flags.culinary_wc_supplier_sync_ran = True

        existing_wc_id = getattr(doc, "custom_woocommerce_category_id", None)
        name = getattr(doc, "supplier_name", None) or getattr(doc, "name", None) or ""
        image_src = _build_image_src(getattr(doc, "image", None))
        slug = getattr(doc, "custom_woocommerce_slug", None) or (name.lower().replace(" ", "-") if name else None)
        
        # Vendor kategori ID'sini dinamik olarak al
        parent_id = get_vendor_category_id()
        if not parent_id:
            frappe.throw(frappe._("Lütfen 'Vendor' ürün grubunu oluşturun ve WooCommerce kategori ID'sini tanımlayın"))
        
        print(f"\n\n\n DEBUG:1 exixting Category id: {existing_wc_id}")
        print(f"\n\n\n DEBUG:1 Vendor parent_id: {parent_id}")

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
                    title="Portal Supplier Category Update Failed",
                    message=f"Failed to update category {existing_wc_id} for Supplier {doc.name}",
                )
        else:
            print("\n\n\n DEBUG 2 No category Id")
            print(f"\n\n\n DEBUG:4 name: {name}, parent_id: {parent_id}")
            wc_category_id = _post_wc_category(name=name,  parent_id=parent_id)
            print(f"\n\n\n DEBUG:3 wc_category_id: {wc_category_id}")
            if wc_category_id:
                try:
                    frappe.db.set_value("Supplier", doc.name, "custom_woocommerce_category_id", wc_category_id)
                    frappe.db.commit()
                except Exception:
                    frappe.log_error(
                        title="Supplier Portal Category ID Update Error",
                        message=frappe.get_traceback(),
                    )
    except Exception:
        frappe.log_error(
            title="Supplier Portal Category Sync Error",
            message=frappe.get_traceback(),
        )


def handle_supplier_on_trash(doc, method=None):
    """Supplier silindiğinde Portal'teki karşılık gelen kategoriyi de siler."""
    try:
        existing_wc_id = getattr(doc, "custom_woocommerce_category_id", None)
        if existing_wc_id:
            deleted = _delete_wc_category(existing_wc_id)
            if not deleted:
                frappe.log_error(
                    title="Portal Supplier Category Delete Failed",
                    message=f"Failed to delete category {existing_wc_id} for Supplier {doc.name}",
                )
    except Exception:
        frappe.log_error(
            title="Supplier Portal Category Delete Sync Error",
            message=frappe.get_traceback(),
        )


def _fetch_all_dokan_stores():
    """Dokan API'den tüm store'ları çeker ve cache'ler"""
    url = f"{get_wo_url()}/wp-json/dokan/v1/stores"
    
    all_stores = []
    page = 1
    per_page = 100
    
    while True:
        try:
            resp = requests.get(
                url,
                auth=(get_wp_user(), get_wp_app_key()),
                params={"per_page": per_page, "page": page},
                headers={"Content-Type": "application/json"},
                timeout=40,
            )
            
            if resp.status_code != 200:
                frappe.log_error(
                    title="Dokan Stores Fetch Error",
                    message=f"Status: {resp.status_code}\nResponse: {resp.text}"
                )
                break
            
            stores = resp.json()
            
            if not isinstance(stores, list) or len(stores) == 0:
                break
            
            all_stores.extend(stores)
            
            # Eğer gelen kayıt sayısı per_page'den azsa, son sayfa
            if len(stores) < per_page:
                break
                
            page += 1
            
        except Exception as e:
            frappe.log_error(
                title="Dokan Stores Fetch Exception",
                message=frappe.get_traceback()
            )
            break
    
    return all_stores


@frappe.whitelist()
def sync_dokan_vendor_id(supplier_name):
    """Dokan Store API'den store'ları çeker ve supplier_name ile eşleştirerek ID'yi döndürür"""
    try:
        if not supplier_name:
            return {"status": "error", "message": frappe._("Supplier name not found")}
        
        # Supplier'ı al
        supplier_doc = frappe.get_doc("Supplier", supplier_name)
        supplier_display_name = supplier_doc.supplier_name or supplier_name
        
        # Tüm store'ları çek
        stores = _fetch_all_dokan_stores()
        
        if not stores:
            return {
                "status": "error",
                "message": frappe._("Could not fetch Dokan Stores")
            }
        
        print(f"\n\n\n DEBUG: Total stores found: {len(stores)}")
        
        # Store'ları supplier_name ile eşleştir
        matched_store = None
        for store in stores:
            store_name = store.get("store_name", "")
            store_id = store.get("id")
            
            # Tam eşleşme kontrolü
            if store_name.lower().strip() == supplier_display_name.lower().strip():
                matched_store = store
                break
        
        if matched_store:
            vendor_id = matched_store.get("id")
            
            # Supplier'a vendor ID'yi kaydet
            frappe.db.set_value("Supplier", supplier_name, "custom_woocommerce_vendor_id", vendor_id)
            frappe.db.commit()
            
            print(f"\n\n\n DEBUG: Matched! Vendor ID {vendor_id} saved to Supplier {supplier_name}")
            
            return {
                "status": "success",
                "message": frappe._("Dokan Vendor found and matched"),
                "vendor_id": vendor_id,
                "store_name": matched_store.get("store_name")
            }
        else:
            return {
                "status": "not_found",
                "message": frappe._("No Dokan Store found with name '{0}'").format(supplier_display_name),
                "searched_name": supplier_display_name,
                "total_stores": len(stores)
            }
            
    except Exception as e:
        frappe.log_error(
            title="Dokan Vendor Sync Error",
            message=frappe.get_traceback()
        )
        return {
            "status": "error",
            "message": frappe._("Error: {0}").format(str(e))
        }


@frappe.whitelist()
def bulk_sync_dokan_vendors(supplier_names):
    """Toplu Supplier için Dokan Vendor eşleştirmesi yapar"""
    try:
        import json
        
        # String ise JSON parse et
        if isinstance(supplier_names, str):
            supplier_names = json.loads(supplier_names)
        
        if not supplier_names or not isinstance(supplier_names, list):
            return {
                "status": "error",
                "message": frappe._("Valid supplier list not found")
            }
        
        # Tüm store'ları bir kez çek (performans için)
        all_stores = _fetch_all_dokan_stores()
        
        if not all_stores:
            return {
                "status": "error",
                "message": frappe._("Could not fetch Dokan Stores")
            }
        
        print(f"\n\n\n DEBUG: Total Dokan stores: {len(all_stores)}")
        print(f"\n\n\n DEBUG: Total suppliers to sync: {len(supplier_names)}")
        
        # Store'ları dict'e çevir (hızlı arama için)
        stores_dict = {}
        for store in all_stores:
            store_name = store.get("store_name", "").lower().strip()
            if store_name:
                stores_dict[store_name] = store
        
        success_count = 0
        not_found_count = 0
        error_count = 0
        results = []
        
        for supplier_name in supplier_names:
            try:
                supplier_doc = frappe.get_doc("Supplier", supplier_name)
                supplier_display_name = supplier_doc.supplier_name or supplier_name
                search_key = supplier_display_name.lower().strip()
                
                # Eşleşme kontrolü
                if search_key in stores_dict:
                    matched_store = stores_dict[search_key]
                    vendor_id = matched_store.get("id")
                    
                    # Supplier'a vendor ID'yi kaydet
                    frappe.db.set_value("Supplier", supplier_name, "custom_woocommerce_vendor_id", vendor_id)
                    
                    success_count += 1
                    results.append({
                        "supplier": supplier_name,
                        "status": "success",
                        "vendor_id": vendor_id,
                        "store_name": matched_store.get("store_name")
                    })
                    
                    print(f"✅ Matched: {supplier_name} -> Vendor ID: {vendor_id}")
                    
                else:
                    not_found_count += 1
                    results.append({
                        "supplier": supplier_name,
                        "status": "not_found",
                        "searched_name": supplier_display_name
                    })
                    
                    print(f"⚠️ Not found: {supplier_name} ({supplier_display_name})")
                    
            except Exception as e:
                error_count += 1
                results.append({
                    "supplier": supplier_name,
                    "status": "error",
                    "error": str(e)
                })
                print(f"❌ Error: {supplier_name} - {str(e)}")
        
        # Değişiklikleri kaydet
        frappe.db.commit()
        
        # Özet mesaj
        message = frappe._("✅ Matched: {0}<br>⚠️ Not Found: {1}<br>❌ Error: {2}").format(
            success_count, not_found_count, error_count
        )
        
        # Detaylı sonuçlar (ilk 10 bulunamayan)
        not_found_list = [r for r in results if r["status"] == "not_found"]
        if not_found_list and len(not_found_list) <= 10:
            message += f"<br><br><strong>{frappe._('Not Found')}:</strong><br>"
            for item in not_found_list:
                message += f"- {item['supplier']} ({item['searched_name']})<br>"
        elif not_found_list:
            message += f"<br><br><em>{frappe._('First 10 not found')}:</em><br>"
            for item in not_found_list[:10]:
                message += f"- {item['supplier']} ({item['searched_name']})<br>"
        
        return {
            "status": "success" if error_count == 0 else "partial",
            "message": message,
            "success_count": success_count,
            "not_found_count": not_found_count,
            "error_count": error_count,
            "results": results
        }
        
    except Exception as e:
        frappe.log_error(
            title="Bulk Dokan Vendor Sync Error",
            message=frappe.get_traceback()
        )
        return {
            "status": "error",
            "message": frappe._("Bulk sync error: {0}").format(str(e))
        }


@frappe.whitelist()
def toggle_customer_status(customer_name):
    """Customer'ı approve eder - custom_role'ü ve WordPress role'ünü 'customer' yapar"""
    try:
        if not customer_name:
            return {"status": "error", "message": frappe._("Customer name not found")}
        
        # Customer dokümantını al (get_doc ile - hooks'ları tetiklemek için)
        customer_doc = frappe.get_doc("Customer", customer_name)
        
        if not customer_doc:
            return {
                "status": "error",
                "message": frappe._("Customer not found: '{0}'").format(customer_name)
            }
        
        customer_display_name = customer_doc.customer_name or customer_name
        
        # WordPress User ID'yi al - custom_portal_user_id'yi direkt kullan
        wp_user_id = customer_doc.custom_portal_user_id
        
        # custom_portal_user_id kontrolü
        if not wp_user_id or wp_user_id == 0:
            return {
                "status": "error",
                "message": frappe._("Customer does not have WordPress User ID (custom_portal_user_id)")
            }
        
        # Yeni role ve disabled durumu
        new_role = "customer"
        new_disabled = 0  # Enable customer
        
        print(f"\n\n\n DEBUG: toggle_customer_status - Customer: {customer_name}, WP User ID: {wp_user_id}")
        
        # WordPress User API'ye PUT isteği at (role güncellemesi için)
        url = f"{get_wo_url()}/wp-json/wp/v2/users/{wp_user_id}"
        payload = {"roles": [new_role]}
        
        print(f"\n\n\n DEBUG: WordPress Update - URL: {url}")
        print(f"\n\n\n DEBUG: WordPress Update - Payload: {payload}")
        
        resp = requests.put(
            url,
            auth=(get_wp_user(), get_wp_app_key()),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        
        print(f"\n\n\n DEBUG: WordPress Update - Status: {resp.status_code}")
        print(f"\n\n\n DEBUG: WordPress Update - Response: {resp.text}")
        
        if resp.status_code not in (200, 201):
            error_message = frappe._("Failed to update customer role in WordPress.")
            
            # 404 hatası özel mesaj
            if resp.status_code == 404:
                error_message = frappe._("WordPress User ID ({0}) not found. Please check custom_portal_user_id field.").format(wp_user_id)
            else:
                error_message = frappe._("Failed to update customer role in WordPress. Status: {0}").format(resp.status_code)
            
            frappe.log_error(
                title="Customer Approve Error",
                message=f"Customer: {customer_name}\nUser ID: {wp_user_id}\nEmail: {customer_doc.email_id}\nStatus: {resp.status_code}\nResponse: {resp.text}",
            )
            return {
                "status": "error",
                "message": error_message
            }
        
        # Customer dokümantındaki custom_role ve disabled alanlarını güncelle
        # NOT: Artık frappe.db.set_value yerine doc.save() kullanıyoruz
        # Bu sayede on_update hooks'ları tetiklenir ve mail gönderilir
        customer_doc.custom_role = new_role
        customer_doc.disabled = new_disabled
        
        # Skip WordPress sync flag'i set et (çünkü zaten yukarıda WordPress'e istek attık)
        customer_doc.flags.skip_wordpress_sync = True
        
        # Kaydet - bu on_update hooks'larını tetikleyecek
        customer_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": frappe._("Customer '{0}' has been approved successfully").format(customer_display_name),
            "customer_name": customer_display_name,
            "disabled": new_disabled,
            "custom_role": new_role
        }
        
    except Exception as e:
        frappe.log_error(
            title="Customer Approve Exception",
            message=frappe.get_traceback()
        )
        return {
            "status": "error",
            "message": frappe._("Error: {0}").format(str(e))
        }
