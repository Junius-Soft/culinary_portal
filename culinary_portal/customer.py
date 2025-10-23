import frappe
import requests
import base64
try:
    # Önce paket altındaki config'i dene
    from wp_integration.wp_integration import config as wp_cfg  # type: ignore
except Exception:
    try:
        # Uyum için üst düzey config'e geri düş
        from wp_integration import config as wp_cfg  # type: ignore
    except Exception:
        wp_cfg = None  # Son aşamada frappe.conf'dan okunur


# -----------------------------
# Çekirdek yardımcılar (yerel, bağımsız)
# -----------------------------

def _safe_json_loads(value):
    """
    (TR) Gerekirse JSON string'i Python dict'e çevirir; zaten dict ise aynen döner.
    Hatalı JSON durumunda hata yükseltir ve erken görünür hale getirir.

    (EN) Parse JSON string to dict if needed; pass-through dicts.
    Raises on invalid JSON to surface issues early.
    """
    if isinstance(value, str):
        import json
        return json.loads(value)
    return value


def _append_role_if_exists(user_doc, role_name):
    """
    (TR) Sistemde var olan rolü `User` dokümanına ekler. Rol yoksa sessizce geçer.

    (EN) Append a role to a `User` doc only if the role exists in the system.
    """
    try:
        if frappe.db.exists("Role", role_name):
            user_doc.append("roles", {"role": role_name})
    except Exception:
        # Ignore non-critical role append errors
        pass


@frappe.whitelist(allow_guest=True)
def create_user_from_wp(payload):
    """
    (TR) WordPress'ten gelen kullanıcı verisiyle ERPNext'te Website User oluşturur.
    Beklenen alanlar: email, username, first_name, last_name, (ops.) roles.
    Mevcut kullanıcı varsa tekrar oluşturmaz.

    (EN) Create a Website User in ERPNext from WordPress user payload.
    Expected keys: email, username, first_name, last_name, (opt.) roles.
    Skips creation if user already exists.
    """
    try:
        data = _safe_json_loads(payload)

        # Validate basics
        for key in ["email", "username", "first_name", "last_name"]:
            if not data.get(key):
                return {"success": False, "error": f"Missing required field: {key}"}

        # Duplicate check
        if frappe.db.exists("User", {"email": data["email"]}):
            return {"success": True, "message": "User already exists", "email": data["email"]}

        # Build new user doc
        user_doc = frappe.get_doc({
            "doctype": "User",
            "email": data["email"],
            "first_name": data.get("first_name", ""),
            "last_name": data.get("last_name", ""),
            "username": data.get("username", data["email"]),
            "enabled": 1,
            "send_welcome_email": 0,
            "user_type": "Website User",
            "language": data.get("language", "en"),
            "time_zone": data.get("time_zone", "Asia/Istanbul"),
            "phone": data.get("phone"),
            "mobile_no": data.get("mobile_no"),
            "bio": data.get("description", ""),
            "wp_user_id": data.get("id"),
            "wp_username": data.get("username"),
            "wp_roles": data.get("roles", []),
            "wp_registered_date": data.get("date_created"),
            "wp_last_login": data.get("last_login"),
        })

        # Assign common roles when available
        for role in ["Customer", "Website User"]:
            _append_role_if_exists(user_doc, role)

        user_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message": f"User created: {user_doc.name}",
            "user_id": user_doc.name,
            "email": user_doc.email,
        }
    except Exception as e:
        frappe.log_error(f"create_user_from_wp error: {frappe.get_traceback()}")
        frappe.db.rollback()
        return {"success": False, "error": str(e), "message": "User oluşturulurken hata oluştu"}


@frappe.whitelist(allow_guest=True)
def update_user_from_wp(payload):
    """
    (TR) WordPress verisiyle ERPNext'teki mevcut User kaydını günceller.
    Eşleşme email veya wp_user_id ile yapılır.

    (EN) Update an existing ERPNext User from WordPress payload by email/wp_user_id.
    """
    try:
        data = _safe_json_loads(payload)

        wp_user_id = data.get("id")
        email = data.get("email")

        user_name = None
        if wp_user_id:
            user_name = frappe.db.get_value("User", {"wp_user_id": wp_user_id}, "name")
        if not user_name and email:
            user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            return {"success": False, "error": "User not found"}

        user_doc = frappe.get_doc("User", user_name)
        fields = {
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "username": data.get("username"),
            "language": data.get("language"),
            "time_zone": data.get("time_zone"),
            "phone": data.get("phone"),
            "mobile_no": data.get("mobile_no"),
            "bio": data.get("description"),
            "website": data.get("website"),
            "wp_roles": data.get("roles", []),
            "wp_last_login": data.get("last_login"),
        }
        for k, v in fields.items():
            if v is not None:
                user_doc.set(k, v)

        user_doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "message": f"User updated: {user_doc.name}", "user_id": user_doc.name}
    except Exception as e:
        frappe.log_error(f"update_user_from_wp error: {frappe.get_traceback()}")
        frappe.db.rollback()
        return {"success": False, "error": str(e), "message": "User güncellenirken hata oluştu"}


@frappe.whitelist(allow_guest=True)
def deactivate_user_from_wp(payload):
    """
    (TR) WordPress tarafında kullanıcı silindiğinde ERPNext User'ı deaktif eder.
    Eşleşme email veya wp_user_id ile yapılır.

    (EN) Deactivate the ERPNext User when WordPress user is deleted.
    """
    try:
        data = _safe_json_loads(payload)
        wp_user_id = data.get("id")
        email = data.get("email")

        user_name = None
        if wp_user_id:
            user_name = frappe.db.get_value("User", {"wp_user_id": wp_user_id}, "name")
        if not user_name and email:
            user_name = frappe.db.get_value("User", {"email": email}, "name")
        if not user_name:
            return {"success": False, "error": "User not found"}

        user_doc = frappe.get_doc("User", user_name)
        user_doc.enabled = 0
        user_doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "message": f"User deactivated: {user_doc.name}", "user_id": user_doc.name}
    except Exception as e:
        frappe.log_error(f"deactivate_user_from_wp error: {frappe.get_traceback()}")
        frappe.db.rollback()
        return {"success": False, "error": str(e), "message": "User deaktive edilirken hata oluştu"}


@frappe.whitelist(allow_guest=True)
def create_customer_and_contact_from_wp(payload):
    """
    (TR) WordPress kullanıcı verisinden ERPNext'te `Customer` ve bağlı `Contact` oluşturur.
    Email zorunludur. Aynı email'e bağlı bir Contact/Customer varsa tekrar oluşturmaz.

    (EN) Create Customer and linked Contact from WordPress user payload.
    Requires email. Skips if a matching Contact/Customer already exists.
    """
    try:
        data = _safe_json_loads(payload)
        email = data.get("email")
        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or ""
        phone = data.get("phone") or data.get("mobile_no") or ""

        if not email:
            return {"success": False, "error": "Email required"}

        existing_contact = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
        if existing_contact:
            link_name = frappe.db.get_value(
                "Dynamic Link", {"parent": existing_contact, "link_doctype": "Customer"}, "link_name"
            )
            if link_name:
                return {"success": True, "message": "Customer already exists", "customer": link_name, "contact": existing_contact}

        full_name = (f"{first_name} {last_name}".strip()) or email.split('@')[0]

        customer_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": full_name,
            "customer_type": "Individual",
            "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups",
            "territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
            "email_id": email,
        })
        customer_doc.insert(ignore_permissions=True)

        contact_doc = frappe.get_doc({
            "doctype": "Contact",
            "first_name": first_name or full_name,
            "last_name": last_name,
            "email_ids": [{"email_id": email, "is_primary": 1}],
            "phone_nos": ([{"phone": phone, "is_primary_phone": 1}] if phone else []),
            "links": [{"link_doctype": "Customer", "link_name": customer_doc.name}],
        })
        contact_doc.insert(ignore_permissions=True)

        frappe.db.commit()
        return {"success": True, "message": "Customer & Contact created", "customer": customer_doc.name, "contact": contact_doc.name}
    except Exception as e:
        frappe.log_error(f"create_customer_and_contact_from_wp error: {frappe.get_traceback()}")
        frappe.db.rollback()
        return {"success": False, "error": str(e), "message": "Customer/Contact oluşturulurken hata oluştu"}


# -----------------------------
# Genel erişilebilir endpoint'ler (public endpoints)
# -----------------------------

# -----------------------------
# WooCommerce (WordPress) senkronizasyon yardımcıları
# -----------------------------

def _get_wc_cfg():
    """
    (TR) WooCommerce yapılandırmasını güvenli şekilde döndürür.
    Önce modül config, yoksa site config (frappe.conf) okunur.
    """
    url = None
    ck = None
    cs = None
    # Modül bazlı
    if wp_cfg and hasattr(wp_cfg, "WC_API_URL"):
        url = getattr(wp_cfg, "WC_API_URL", None)
        ck = getattr(wp_cfg, "WC_CONSUMER_KEY", None)
        cs = getattr(wp_cfg, "WC_CONSUMER_SECRET", None)
    # Site config fallback
    if not url:
        url = frappe.conf.get("WC_API_URL")
    if not ck:
        ck = frappe.conf.get("WC_CONSUMER_KEY")
    if not cs:
        cs = frappe.conf.get("WC_CONSUMER_SECRET")
    return url, ck, cs


def _wc_headers():
    """
    (TR) WooCommerce Basic Auth header'ı üretir.
    """
    _, ck, cs = _get_wc_cfg()
    if not (ck and cs):
        raise RuntimeError("WooCommerce credentials missing. Set in config or site config.")
    credentials = f"{ck}:{cs}"
    token = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _wc_base(url_path: str) -> str:
    url, _, _ = _get_wc_cfg()
    if not url:
        raise RuntimeError("WooCommerce API URL missing. Set WC_API_URL in config or site config.")
    return f"{url.rstrip('/')}/{url_path.lstrip('/')}"


def sync_user_to_wp_create(user_doc):
    """
    (TR) ERP'de yeni User oluşturulduğunda WooCommerce'e müşteri olarak gönderir.
    """
    try:
        payload = {
            "email": user_doc.email,
            "username": user_doc.username or user_doc.email,
            "first_name": user_doc.first_name or "",
            "last_name": user_doc.last_name or "",
        }
        r = requests.post(_wc_base("customers"), headers=_wc_headers(), json=payload, timeout=20)
        if r.status_code in (200, 201):
            data = r.json()
            # WooCommerce customer id'yi saklayalım (ileri senk için)
            if data.get("id"):
                frappe.db.set_value("User", user_doc.name, "wp_customer_id", data["id"], update_modified=False)
                frappe.db.commit()
        else:
            frappe.log_error(f"WC create customer failed: {r.status_code} - {r.text}")
    except Exception:
        frappe.log_error(f"WC create customer exception: {frappe.get_traceback()}")


def sync_user_to_wp_update(user_doc):
    """
    (TR) ERP'de User güncellendiğinde WooCommerce müşterisini günceller.
    """
    try:
        wc_id = getattr(user_doc, "wp_customer_id", None)
        if not wc_id:
            # Yoksa email ile bulmayı deneyelim
            r_search = requests.get(_wc_base("customers"), headers=_wc_headers(), params={"email": user_doc.email}, timeout=20)
            if r_search.status_code == 200 and isinstance(r_search.json(), list) and r_search.json():
                wc_id = r_search.json()[0].get("id")
        if not wc_id:
            return
        payload = {
            "email": user_doc.email,
            "first_name": user_doc.first_name or "",
            "last_name": user_doc.last_name or "",
            "username": user_doc.username or user_doc.email,
        }
        r = requests.put(_wc_base(f"customers/{wc_id}"), headers=_wc_headers(), json=payload, timeout=20)
        if r.status_code not in (200, 201):
            frappe.log_error(f"WC update customer failed: {r.status_code} - {r.text}")
    except Exception:
        frappe.log_error(f"WC update customer exception: {frappe.get_traceback()}")


def sync_user_to_wp_delete(user_doc):
    """
    (TR) ERP'de User silindiğinde WooCommerce müşterisini siler (force=false, trash'e taşır).
    """
    try:
        wc_id = getattr(user_doc, "wp_customer_id", None)
        if not wc_id:
            r_search = requests.get(_wc_base("customers"), headers=_wc_headers(), params={"email": user_doc.email}, timeout=20)
            if r_search.status_code == 200 and isinstance(r_search.json(), list) and r_search.json():
                wc_id = r_search.json()[0].get("id")
        if not wc_id:
            return
        r = requests.delete(_wc_base(f"customers/{wc_id}"), headers=_wc_headers(), params={"force": False}, timeout=20)
        if r.status_code not in (200, 201):
            frappe.log_error(f"WC delete customer failed: {r.status_code} - {r.text}")
    except Exception:
        frappe.log_error(f"WC delete customer exception: {frappe.get_traceback()}")


def sync_customer_to_wp_delete(customer_doc):
    """
    (TR) ERP'de Customer silindiğinde ilgili WooCommerce müşterisini de siler.
    Eşleştirme için `Customer.email_id` kullanılır. force=false ile çöp kutusuna taşır.
    """
    try:
        email = (
            customer_doc.get("email_id") if isinstance(customer_doc, dict) else getattr(customer_doc, "email_id", None)
        )
        if not email:
            return
        # Email ile WooCommerce'te müşteri ara
        r_search = requests.get(_wc_base("customers"), headers=_wc_headers(), params={"email": email}, timeout=20)
        if r_search.status_code == 200 and isinstance(r_search.json(), list) and r_search.json():
            wc_id = r_search.json()[0].get("id")
            if wc_id:
                r = requests.delete(_wc_base(f"customers/{wc_id}"), headers=_wc_headers(), params={"force": False}, timeout=20)
                if r.status_code not in (200, 201):
                    frappe.log_error(f"WC delete by customer failed: {r.status_code} - {r.text}")
        else:
            # Bulunamadı; logla ama hata yükseltme
            frappe.log_error(f"WC customer not found for email {email} during ERP delete")
    except Exception:
        frappe.log_error(f"WC delete customer (from Customer.on_trash) exception: {frappe.get_traceback()}")


def enqueue_sync_customer_to_wp_delete(doc, method=None):
    """
    (TR) Hook üzerinden çağrılan hafif fonksiyon. Silmeyi arka planda kuyruğa alır.
    """
    try:
        frappe.enqueue(
            "wp_integration.api.customer.sync_customer_to_wp_delete",
            queue="short",
            job_name=f"wc_delete_customer_{getattr(doc, 'name', '')}",
            customer_doc=doc.as_dict(),
            now=False
        )
    except Exception:
        # Asla silmeyi bloke etme
        frappe.log_error(f"Enqueue WC delete failed: {frappe.get_traceback()}")

@frappe.whitelist(allow_guest=True, methods=["POST"])
def wp_user_webhook():
    """
    (TR) WordPress'ten gelen kullanıcı event'lerini kabul eden webhook endpoint'i.
    Event'e göre sırasıyla User oluşturur/günceller/deaktif eder ve `Customer+Contact` oluşturur.
    Beklenen event değerleri: `user.created`, `user.updated`, `user.deleted`.

    (EN) Webhook endpoint that accepts WordPress user events and triggers local
    handlers to create/update/deactivate `User` and create `Customer+Contact`.
    Expected events: `user.created`, `user.updated`, `user.deleted`.
    """
    try:
        if frappe.request.method != 'POST':
            return {"success": False, "error": "Method not allowed", "message": "Sadece POST method kabul edilir"}

        try:
            payload = frappe.request.get_json()
        except Exception:
            payload = frappe.form_dict
        if not payload:
            return {"success": False, "error": "No data received"}

        event_type = payload.get('event', 'user.created')
        data = payload.get('data', payload)

        if event_type == 'user.created':
            user_res = create_user_from_wp(data)
            try:
                create_customer_and_contact_from_wp(data)
            except Exception as customer_err:
                frappe.log_error(f"create_customer_and_contact_from_wp failed: {str(customer_err)}")
            return user_res

        if event_type == 'user.updated':
            return update_user_from_wp(data)

        if event_type == 'user.deleted':
            return deactivate_user_from_wp(data)

        return {"success": False, "error": "Unknown event type", "message": f"Bilinmeyen event tipi: {event_type}"}
    except Exception as e:
        frappe.log_error(f"wp_user_webhook error: {frappe.get_traceback()}")
        return {"success": False, "error": str(e), "message": "Webhook işlenirken hata oluştu"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_customer_from_wp_user():
    """
    (TR) Manuel test endpoint'i. WordPress'e ihtiyaç duymadan, gönderilen JSON ile
    doğrudan `Customer + Contact` oluşturur.

    (EN) Manual test endpoint. Creates `Customer + Contact` directly from the
    posted JSON without needing WordPress.
    """
    try:
        data = frappe.request.get_json()
    except Exception:
        data = frappe.form_dict
    return create_customer_and_contact_from_wp(data)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_customer_from_restaurant():
    """
    Restaurant Registration formundan gelen verilerle ERPNext'te Customer, Address ve Contact oluşturur.
    Webhook URL: POST /api/method/wp_integration.api.customer.create_customer_from_restaurant
    
    Beklenen payload formatı: Restaurant Registration Form
    """
    try:
        # Request'ten veriyi al
        if frappe.request.method != 'POST':
            return {
                "success": False,
                "error": "Method not allowed",
                "message": "Sadece POST method kabul edilir"
            }
        
        # JSON verisini al
        data = None
        try:
            data = frappe.request.get_json()
        except Exception:
            pass
        
        if not data:
            data = frappe.form_dict
        
        # Frappe _dict'i normal dict'e çevir
        if data and hasattr(data, 'items'):
            data = dict(data)
        
        if not data:
            return {
                "success": False,
                "error": "No data received",
                "message": "Veri alınamadı"
            }
        
        # Debug: Gelen veriyi logla
        print(f"<<<<<< Restaurant Customer webhook received with {len(data)} keys")
        print(f"<<<<<< First 10 keys: {list(data.keys())[:10]}")
        print(f"<<<<<< text_2 (company): {data.get('text_2')}")
        print(f"<<<<<< email_1: {data.get('email_1')}")
        
        import json
        frappe.log_error(
            title="Restaurant Customer Webhook Received",
            message=f"Data received:\n{json.dumps(data, indent=2, default=str)}"
        )
        
        # Zorunlu alanları kontrol et
        company_name = data.get('text_2', '').strip()
        email = data.get('email_1', '').strip()
        
        if not company_name:
            return {
                "success": False,
                "error": "Company name required",
                "message": "Şirket adı zorunludur"
            }
        
        if not email:
            return {
                "success": False,
                "error": "Email required",
                "message": "E-mail zorunludur"
            }
        
        # Aynı email ile Customer var mı kontrol et
        existing_customer = frappe.db.get_value("Customer", {"email_id": email}, "name")
        if existing_customer:
            return {
                "success": True,
                "message": "Customer zaten mevcut",
                "customer_name": existing_customer,
                "already_exists": True
            }
        
        # Address alanlarını parse et
        address_data = {}
        
        # JSON string kontrolü
        if data.get('address_1') and isinstance(data.get('address_1'), str):
            try:
                import json
                address_data = json.loads(data.get('address_1'))
            except:
                pass
        
        # JSON yoksa ayrı alanlardan al
        if not address_data:
            if data.get('address_1_street_address'):
                address_data = {
                    'street_address': data.get('address_1_street_address', ''),
                    'address_line': data.get('address_1_address_line', ''),
                    'city': data.get('address_1_city', ''),
                    'state': data.get('address_1_state', ''),
                    'zip': data.get('address_1_zip', '')
                }
        
        # Customer oluştur
        customer_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": company_name,
            "customer_type": "Company",
            "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups",
            "territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
            "email_id": email,
            #"custom_portal_email": email,  # Yerel ERP deki Portal email alanına da kaydet
            "woocommerce_identifier": email,  # Portal email alanına da kaydet
            "mobile_no": data.get('phone_1', ''),
            "tax_id": data.get('text_3', ''),
            "custom_company_type": data.get('select_1', ''),
            "custom_ust_id": data.get('text_4', ''),
        })
        customer_doc.insert(ignore_permissions=True)
        
        print(f"Customer created: {customer_doc.name}")
        
        # Address oluştur
        address_doc = None
        if address_data.get('street_address') or address_data.get('city'):
            # Country field'ını validate et
            country_value = data.get('select_2', 'Germany')
            
            # Eğer geçersiz bir değerse (one, two, vb.) Germany kullan
            if not frappe.db.exists("Country", country_value):
                print(f"Invalid country '{country_value}', using Germany as default")
                country_value = "Germany"
            
            address_doc = frappe.get_doc({
                "doctype": "Address",
                "address_title": company_name,
                "address_type": "Billing",
                "address_line1": address_data.get('street_address', ''),
                "address_line2": address_data.get('address_line', ''),
                "city": address_data.get('city', ''),
                "state": address_data.get('state', ''),
                "pincode": address_data.get('zip', ''),
                "country": country_value,
                "links": [{"link_doctype": "Customer", "link_name": customer_doc.name}]
            })
            address_doc.insert(ignore_permissions=True)
            print(f"Address created: {address_doc.name}")
        
        # Contact oluştur (Firmenvertreter)
        contact_doc = None
        firmenvertreter_name = data.get('text_7', '').strip()
        firmenvertreter_mail = data.get('email_2', '').strip()
        firmenvertreter_phone = data.get('phone_2', '').strip()
        
        if firmenvertreter_name and firmenvertreter_mail:
            contact_doc = frappe.get_doc({
                "doctype": "Contact",
                "first_name": firmenvertreter_name,
                "email_ids": [{"email_id": firmenvertreter_mail, "is_primary": 1}],
                "phone_nos": ([{"phone": firmenvertreter_phone, "is_primary_phone": 1}] if firmenvertreter_phone else []),
                "links": [{"link_doctype": "Customer", "link_name": customer_doc.name}],
            })
            contact_doc.insert(ignore_permissions=True)
            print(f"Contact created: {contact_doc.name}")
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Customer başarıyla oluşturuldu",
            "customer_name": customer_doc.name,
            "address_name": address_doc.name if address_doc else None,
            "contact_name": contact_doc.name if contact_doc else None,
            "data": {
                "customer": customer_doc.name,
                "customer_type": customer_doc.customer_type,
                "email": customer_doc.email_id,
                "mobile": customer_doc.mobile_no,
                "tax_id": customer_doc.tax_id,
                "address": address_doc.name if address_doc else None,
                "contact": contact_doc.name if contact_doc else None
            }
        }
        
    except Exception as e:
        frappe.log_error(
            title="Customer Creation Error", 
            message=f"Restaurant Customer Error: {str(e)}\n{frappe.get_traceback()}"
        )
        frappe.db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "Customer oluşturulurken hata oluştu"
        }

