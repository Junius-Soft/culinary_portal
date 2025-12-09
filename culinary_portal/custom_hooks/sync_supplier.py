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


def _find_wordpress_user_by_email(email):
    """Email ile WordPress user'ı bulur ve user data döner"""
    try:
        if not email:
            print(f"\n\n\n DEBUG: _find_wordpress_user_by_email - Email boş!")
            return None
        
        # WordPress Users API - email ile ara
        url = f"{get_wo_url()}/wp-json/wp/v2/users"
        params = {"search": email}
        
        print(f"\n\n\n DEBUG: Search WP User - Email: {email}, URL: {url}")
        
        resp = requests.get(
            url,
            auth=(get_wp_user(), get_wp_app_key()),
            params=params,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        
        print(f"\n\n\n DEBUG: Search WP User - Status: {resp.status_code}")
        print(f"\n\n\n DEBUG: Search WP User - Response: {resp.text[:500]}")
        
        if resp.status_code == 200:
            users = resp.json()
            print(f"\n\n\n DEBUG: Found {len(users) if isinstance(users, list) else 0} users")
            
            if isinstance(users, list) and len(users) > 0:
                # İlk eşleşen user'ı döndür
                for user in users:
                    user_email = user.get("email", "")
                    user_id = user.get("id")
                    print(f"\n\n\n DEBUG: Checking user - ID: {user_id}, Email: {user_email}")
                    
                    if user_email.lower() == email.lower():
                        print(f"\n\n\n DEBUG: ✅ MATCH! WP User ID: {user_id}, Email: {user_email}")
                        return user
        
        print(f"\n\n\n DEBUG: ❌ WordPress user not found with email: {email}")
        return None
        
    except Exception as e:
        print(f"\n\n\n DEBUG: ❌ Error searching WP user: {str(e)}")
        frappe.log_error(
            title="WordPress User Search Error",
            message=f"Email: {email}\nError: {str(e)}\n{frappe.get_traceback()}"
        )
        return None


@frappe.whitelist()
def debug_customer_info(customer_name):
    """Customer bilgilerini debug için döndürür"""
    try:
        customer_doc = frappe.get_doc("Customer", customer_name)
        
        info = {
            "customer_name": customer_doc.name,
            "customer_display_name": customer_doc.customer_name,
            "email_id": customer_doc.email_id,
            "custom_portal_user_id": customer_doc.custom_portal_user_id,
            "custom_role": customer_doc.custom_role,
            "disabled": customer_doc.disabled,
            "woocommerce_identifier": getattr(customer_doc, "woocommerce_identifier", None)
        }
        
        print(f"\n\n\n DEBUG: Customer Info: {info}")
        
        # WordPress'te email ile ara
        if customer_doc.email_id:
            wp_user = _find_wordpress_user_by_email(customer_doc.email_id)
            if wp_user:
                info["wordpress_user_found"] = True
                info["wordpress_user_id"] = wp_user.get("id")
                info["wordpress_user_email"] = wp_user.get("email")
            else:
                info["wordpress_user_found"] = False
        
        return {"status": "success", "data": info}
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "traceback": frappe.get_traceback()
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
        
        # Güncel dokümanı almak için reload yap (timestamp'i güncellemek için - "Document modified" hatasını önlemek için)
        customer_doc.reload()
        
        customer_display_name = customer_doc.customer_name or customer_name
        customer_email = customer_doc.email_id
        
        # custom_portal_user_id kontrolü
        wp_user_id = customer_doc.custom_portal_user_id
        
        if not wp_user_id or wp_user_id == 0:
            # Email ile WordPress user bul ve custom_portal_user_id'yi güncelle
            if not customer_email:
                return {
                    "status": "error",
                    "message": frappe._("Customer does not have email address and custom_portal_user_id")
                }
            
            print(f"\n\n\n DEBUG: custom_portal_user_id boş, email ile aranıyor: {customer_email}")
            wp_user = _find_wordpress_user_by_email(customer_email)
            
            if not wp_user:
                return {
                    "status": "error",
                    "message": frappe._("WordPress user not found with email: {0}").format(customer_email)
                }
            
            wp_user_id = wp_user.get("id")
            customer_doc.custom_portal_user_id = wp_user_id
            print(f"\n\n\n DEBUG: custom_portal_user_id güncellendi: {wp_user_id}")
        
        print(f"\n\n\n DEBUG: toggle_customer_status - Customer: {customer_name}, custom_portal_user_id: {wp_user_id}")
        
        # Yeni role ve disabled durumu
        new_role = "customer"
        new_disabled = 0  # Enable customer
        
        # WordPress User API'ye PUT isteği at (custom_portal_user_id ile)
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
        
        # WordPress güncelleme durumunu kontrol et
        wordpress_updated = False
        warning_message = None
        
        # Eğer 404 hatası alınırsa, custom_portal_user_id geçersiz demektir
        if resp.status_code == 404:
            print(f"\n\n\n DEBUG: custom_portal_user_id ({wp_user_id}) geçersiz (404)")
            
            # Email ile doğru user'ı bulmaya çalış
            if customer_email:
                print(f"\n\n\n DEBUG: Email ile aranıyor: {customer_email}")
                wp_user = _find_wordpress_user_by_email(customer_email)
                
                if wp_user:
                    # Doğru ID'yi bulduk, güncelle ve tekrar dene
                    wp_user_id = wp_user.get("id")
                    customer_doc.custom_portal_user_id = wp_user_id
                    print(f"\n\n\n DEBUG: custom_portal_user_id düzeltildi: {wp_user_id}")
                    
                    # Tekrar dene
                    url = f"{get_wo_url()}/wp-json/wp/v2/users/{wp_user_id}"
                    resp = requests.put(
                        url,
                        auth=(get_wp_user(), get_wp_app_key()),
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=40,
                    )
                    
                    print(f"\n\n\n DEBUG: Retry - Status: {resp.status_code}")
                    
                    if resp.status_code in (200, 201):
                        wordpress_updated = True
                    else:
                        warning_message = frappe._("WordPress user found but update failed. Customer approved in Frappe only.")
                else:
                    warning_message = frappe._("WordPress user not found. Customer approved in Frappe only.")
            else:
                warning_message = frappe._("No email found to search WordPress user. Customer approved in Frappe only.")
            
            # WordPress güncellenemese bile devam et - Frappe'de güncelle
            if not wordpress_updated:
                frappe.log_error(
                    title="Customer Approve - WordPress Update Failed",
                    message=f"Customer: {customer_name}\nUser ID: {wp_user_id}\nEmail: {customer_email}\nWordPress update failed but proceeding with Frappe update",
                )
        
        elif resp.status_code not in (200, 201):
            # Başka bir hata - yine de Frappe'de güncelle ama uyarı ver
            warning_message = frappe._("WordPress update failed (Status: {0}). Customer approved in Frappe only.").format(resp.status_code)
            frappe.log_error(
                title="Customer Approve - WordPress Error",
                message=f"Customer: {customer_name}\nUser ID: {wp_user_id}\nEmail: {customer_email}\nStatus: {resp.status_code}\nResponse: {resp.text}",
            )
        else:
            # Başarılı!
            wordpress_updated = True
        
        # Her durumda Customer dokümantını güncelle (WordPress başarısız olsa bile)
        # Bu sayede on_update hooks çalışır ve mail gönderilir
        
        # Save işlemi yapmadan ÖNCE tekrar reload et (timestamp'i kesin olarak güncellemek için)
        # Bu "Document modified" hatasını önler
        customer_doc.reload()
        
        customer_doc.custom_role = new_role
        customer_doc.disabled = new_disabled
        
        # Skip WordPress sync flag'i set et (çünkü zaten yukarıda WordPress'e istek attık)
        customer_doc.flags.skip_wordpress_sync = True
        
        # Kaydet - bu on_update hooks'larını tetikleyecek ve mail gönderilecek
        # "Document modified" hatasını yakalamak için try-except kullan
        max_retries = 3
        saved = False
        for attempt in range(max_retries):
            try:
                customer_doc.save(ignore_permissions=True)
                frappe.db.commit()
                saved = True
                break
            except Exception as save_error:
                error_msg = str(save_error)
                if "Document has been modified" in error_msg or "modified after" in error_msg.lower():
                    # Timestamp uyumsuzluğu var, tekrar reload et ve dene
                    if attempt < max_retries - 1:
                        customer_doc.reload()
                        customer_doc.custom_role = new_role
                        customer_doc.disabled = new_disabled
                        customer_doc.flags.skip_wordpress_sync = True
                        continue
                    else:
                        # Son deneme de başarısız, hatayı logla ve devam et
                        frappe.log_error(
                            title="Customer Approve - Save Retry Failed",
                            message=f"Customer: {customer_name}\nAfter {max_retries} attempts, still getting modified error. Error: {error_msg}"
                        )
                        raise
                else:
                    # Başka bir hata, direkt fırlat
                    raise
        
        if not saved:
            frappe.db.commit()
        
        # Başarı mesajı oluştur
        success_message = frappe._("Customer '{0}' has been approved successfully").format(customer_display_name)
        if warning_message:
            success_message += f"<br><br>⚠️ {warning_message}"
        
        return {
            "status": "success",
            "message": success_message,
            "customer_name": customer_display_name,
            "disabled": new_disabled,
            "custom_role": new_role,
            "wordpress_updated": wordpress_updated
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
