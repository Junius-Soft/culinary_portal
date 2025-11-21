import frappe
import requests
from typing import Optional

from culinary_portal.custom_hooks.create_item import (
    get_wo_url,
    get_wp_user,
    get_wp_app_key
)
# Circular import'u önlemek için lazy import kullan
# from culinary_portal.woocommerce_endpoint import update_wordpress_user_from_customer


def delete_wp_user(portal_user_id: int) -> bool:
    """
    WordPress user'ı siler.
    
    Args:
        portal_user_id: WordPress user ID
        
    Returns:
        Başarılı ise True, aksi halde False
    """
    try:
        # WordPress User Delete endpoint
        url = f"{get_wo_url()}/wp-json/wp/v2/users/{portal_user_id}"
        
        print(f"\n\n\n DEBUG: User Delete - URL: {url}")
        
        # WordPress'e DELETE isteği (force=true ile kalıcı silme)
        resp = requests.delete(
            url,
            auth=(get_wp_user(), get_wp_app_key()),
            params={"force": True, "reassign": 1},  # reassign=1 ile içerikleri başka kullanıcıya ata
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        
        print(f"\n\n\n DEBUG: User Delete - Status: {resp.status_code}")
        print(f"\n\n\n DEBUG: User Delete - Response: {resp.text}")
        
        # Başarılı yanıt kontrolü
        if resp.status_code in (200, 204):
            print(f"\n\n\n DEBUG: User {portal_user_id} başarıyla silindi")
            return True
        else:
            frappe.log_error(
                title="WordPress User Delete Error",
                message=f"User ID: {portal_user_id}\nStatus: {resp.status_code}\nResponse: {resp.text}",
            )
            
    except Exception:
        frappe.log_error(
            title="WordPress User Delete Exception",
            message=frappe.get_traceback(),
        )
    
    return False


def delete_b2b_group(b2b_group_id: int) -> bool:
    """
    Deletes WordPress B2B King Group.
    
    Args:
        b2b_group_id: B2B King Group ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # WordPress B2B Group Delete endpoint
        url = f"{get_wo_url()}/wp-json/wp/v2/b2bking_group/{b2b_group_id}"
        
        print(f"\n\n\n DEBUG: B2B Group Delete - URL: {url}")
        
        # Send DELETE request to WordPress (force=true for permanent deletion)
        resp = requests.delete(
            url,
            auth=(get_wp_user(), get_wp_app_key()),
            params={"force": True},
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        
        print(f"\n\n\n DEBUG: B2B Group Delete - Status: {resp.status_code}")
        print(f"\n\n\n DEBUG: B2B Group Delete - Response: {resp.text}")
        
        # Check successful response
        if resp.status_code in (200, 204):
            print(f"\n\n\n DEBUG: B2B Group {b2b_group_id} deleted successfully")
            return True
        else:
            frappe.log_error(
                title="WordPress B2B Group Delete Error",
                message=f"Group ID: {b2b_group_id}\nStatus: {resp.status_code}\nResponse: {resp.text}",
            )
            
    except Exception:
        frappe.log_error(
            title="WordPress B2B Group Delete Exception",
            message=frappe.get_traceback(),
        )
    
    return False


def update_user_b2b_group(portal_user_id: int, b2b_group_id: int) -> bool:
    """
    WordPress user'ın meta alanına B2B Group ID'yi atar.
    
    Args:
        portal_user_id: WordPress user ID
        b2b_group_id: B2B King Group ID
        
    Returns:
        Başarılı ise True, aksi halde False
    """
    print(f"\n\n\n DEBUG: update_user_b2b_group - portal_user_id: {portal_user_id}, b2b_group_id: {b2b_group_id}")
    try:
        # WordPress User Update endpoint
        url = f"{get_wo_url()}/wp-json/wp/v2/users/{portal_user_id}"
        
        # Gönderilecek payload
        payload = {
            "meta": {
                "b2bking_b2buser":"yes",
                "b2bking_customergroup": [str(b2b_group_id)]
            }
        }
        
        print(f"\n\n\n DEBUG: User Update PUT - URL: {url}")
        print(f"\n\n\n DEBUG: User Update PUT - Payload: {payload}")
        
        # WordPress'e PUT isteği
        resp = requests.put(
            url,
            auth=(get_wp_user(), get_wp_app_key()),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        
        print(f"\n\n\n DEBUG: User Update PUT - Status: {resp.status_code}")
        print(f"\n\n\n DEBUG: User Update PUT - Response: {resp.text}")
        
        # Başarılı yanıt kontrolü
        if resp.status_code in (200, 201):
            print(f"\n\n\n DEBUG: User {portal_user_id} B2B Group {b2b_group_id} ile güncellendi")
            return True
        else:
            frappe.log_error(
                title="User B2B Group Update Error",
                message=f"User ID: {portal_user_id}\nGroup ID: {b2b_group_id}\nStatus: {resp.status_code}\nResponse: {resp.text}",
            )
            
    except Exception:
        frappe.log_error(
            title="User B2B Group Update Exception",
            message=frappe.get_traceback(),
        )
    
    return False


def create_b2b_group(customer_name: str) -> Optional[int]:
    """
    Creates a new B2B King Group in WordPress.
    
    Args:
        customer_name: Customer name from Customer doctype
        
    Returns:
        Created B2B Group ID or None if error
    """
    try:
        # Get Customer document
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_display_name = customer_doc.customer_name or customer_name
        
        # WordPress API endpoint
        url = f"{get_wo_url()}/wp-json/wp/v2/b2bking_group"
        
        # Payload to send
        payload = {
            "status": "publish",
            "title": customer_display_name
        }
        
        # Send POST request to WordPress
        resp = requests.post(
            url,
            auth=(get_wp_user(), get_wp_app_key()),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=40,
        )
        
        print(f"\n\n\n DEBUG: B2B Group POST - Status: {resp.status_code}")
        print(f"\n\n\n DEBUG: B2B Group POST - Response: {resp.text}")
        
        # Check successful response
        if resp.status_code in (200, 201):
            data = resp.json()
            group_id = data.get("id") if isinstance(data, dict) else None
            
            if group_id:
                frappe.msgprint(
                    frappe._("B2B Group created successfully: {0}").format(customer_display_name),
                    indicator="green"
                )
            
            return group_id
        else:
            frappe.log_error(
                title="B2B Group POST Error",
                message=f"Customer: {customer_name}\nStatus: {resp.status_code}\nResponse: {resp.text}",
            )
            frappe.msgprint(
                frappe._("Error occurred while creating B2B Group"),
                indicator="red"
            )
            
    except Exception:
        frappe.log_error(
            title="B2B Group POST Exception",
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            frappe._("An error occurred while creating B2B Group"),
            indicator="red"
        )
    
    return None


def handle_customer_b2b_group(doc, method=None):
    """
    Customer kaydedildiğinde otomatik olarak WordPress'te B2B Group oluşturur.
    Hook tarafından çağrılır.
    """
    try:
        # WordPress webhook update'lerinde atla (sadece create'de çalışsın)
        if getattr(doc.flags, "skip_b2b_group_hook", False):
            print(f"\n\n\n DEBUG: skip_b2b_group_hook flag'i var, B2B Group hook atlanıyor")
            return
        
        # Flag kontrolü - tekrar çalışmasını önle
        if getattr(doc.flags, "culinary_b2b_group_sync_ran", False):
            return
        doc.flags.culinary_b2b_group_sync_ran = True
        
        # Eğer zaten B2B Group ID varsa
        existing_group_id = getattr(doc, "custom_b2b_group_id", None)
        portal_user_id = getattr(doc, "custom_portal_user_id", None)
        
        if existing_group_id:
            print(f"\n\n\n DEBUG: Customer {doc.name} zaten bir B2B Group'a sahip: {existing_group_id}")
            
            # Portal user ID varsa, WordPress user'ı güncelle
            if portal_user_id:
                print(f"\n\n\n DEBUG: WordPress User güncelleniyor (portal_user_id: {portal_user_id})...")
                update_user_b2b_group(portal_user_id=portal_user_id, b2b_group_id=existing_group_id)
            else:
                print(f"\n\n\n DEBUG: Portal User ID bulunamadı, WordPress User güncellenemedi")
            
            return
        
        # B2B Group oluştur
        customer_name = doc.name
        group_id = create_b2b_group(customer_name)
        
        # Oluşturulan Group ID'yi Customer'a kaydet
        if group_id:
            try:
                frappe.db.set_value("Customer", doc.name, "custom_b2b_group_id", group_id)
                frappe.db.commit()
                print(f"\n\n\n DEBUG: B2B Group ID {group_id} Customer {doc.name}'e kaydedildi")
                
                # Portal user ID varsa, WordPress user'ı güncelle
                if portal_user_id:
                    print(f"\n\n\n DEBUG: WordPress User güncelleniyor (yeni group için)...")
                    update_user_b2b_group(portal_user_id=portal_user_id, b2b_group_id=group_id)
                else:
                    print(f"\n\n\n DEBUG: Portal User ID bulunamadı, WordPress User güncellenemedi")
                    
            except Exception:
                frappe.log_error(
                    title="Customer B2B Group ID Update Error",
                    message=frappe.get_traceback(),
                )
                
    except Exception:
        frappe.log_error(
            title="Customer B2B Group Sync Error",
            message=frappe.get_traceback(),
        )


def handle_customer_wordpress_sync(doc, method=None):
	"""
	Customer kaydedildiğinde WordPress user'ı günceller.
	Hook tarafından çağrılır.
	"""
	try:
		# WordPress webhook update'lerinde atla
		if getattr(doc.flags, "skip_wordpress_sync", False):
			return
		
		# Flag kontrolü - tekrar çalışmasını önle
		if getattr(doc.flags, "culinary_wordpress_sync_ran", False):
			return
		doc.flags.culinary_wordpress_sync_ran = True
		
		# Circular import'u önlemek için lazy import
		from culinary_portal.woocommerce_endpoint import update_wordpress_user_from_customer
		
		# WordPress'e güncelleme gönder
		update_wordpress_user_from_customer(doc)
		
	except Exception:
		frappe.log_error(
			title="Customer WordPress Sync Error",
			message=frappe.get_traceback(),
		)


def handle_customer_status_by_role(doc, method=None):
	"""
	Customer kaydedilirken custom_role alanina gore aktif/pasif durumunu ayarlar
	ve role degisikligi yapildiysa flag set eder.
	"""
	try:
		role_value = (doc.custom_role or "").strip()
		if not role_value:
			return

		is_customer_role = role_value.lower() == "customer"
		should_disable = 0 if is_customer_role else 1

		if doc.disabled != should_disable:
			doc.disabled = should_disable

		previous_role = None
		if not doc.get("__islocal"):
			previous_role = frappe.db.get_value("Customer", doc.name, "custom_role") or ""

		if doc.get("__islocal") or (previous_role.strip() != role_value):
			doc.flags.culinary_role_sync_required = True
		else:
			doc.flags.culinary_role_sync_required = getattr(doc.flags, "culinary_role_sync_required", False)
	except Exception:
		frappe.log_error(
			title="Customer Status By Role Error",
			message=frappe.get_traceback(),
		)


def handle_customer_role_sync(doc, method=None):
	"""
	Customer kaydedildikten sonra WordPress user role'unu custom_role ile senkronlar.
	"""
	try:
		if getattr(doc.flags, "skip_wordpress_sync", False):
			return

		role_value = (doc.custom_role or "").strip()
		if not role_value:
			return

		# Role degismediyse DB'den kontrol
		if not getattr(doc.flags, "culinary_role_sync_required", False) and not doc.get("__islocal"):
			prev_role = frappe.db.get_value("Customer", doc.name, "custom_role") or ""
			if prev_role.strip() == role_value:
				return

		wp_user_id = getattr(doc, "custom_portal_user_id", None)
		if not wp_user_id:
			return

		url = f"{get_wo_url()}/wp-json/wp/v2/users/{wp_user_id}"
		payload = {"roles": [role_value]}

		resp = requests.put(
			url,
			auth=(get_wp_user(), get_wp_app_key()),
			json=payload,
			headers={"Content-Type": "application/json"},
			timeout=40,
		)

		if resp.status_code not in (200, 201):
			frappe.log_error(
				title="Customer Role Sync Error",
				message=f"User ID: {wp_user_id}\nRole: {role_value}\nStatus: {resp.status_code}\nResponse: {resp.text}",
			)
			return

		# Disabled state zaten validate'de set edildi; DB'de emniyet icin guncelle
		new_disabled = 0 if role_value.lower() == "customer" else 1
		if frappe.db.get_value("Customer", doc.name, "disabled") != new_disabled:
			frappe.db.set_value("Customer", doc.name, "disabled", new_disabled)
	except Exception:
		frappe.log_error(
			title="Customer Role Sync Exception",
			message=frappe.get_traceback(),
		)


def handle_address_wordpress_sync(doc, method=None):
	"""
	Address güncellendiğinde ilgili Customer kayıtlarını WordPress ile senkronize eder.
	"""
	try:
		if getattr(doc.flags, "skip_wordpress_sync", False):
			return
		
		customer_links = {
			link.link_name
			for link in (doc.links or [])
			if link.link_doctype == "Customer" and link.link_name
		}
		
		if not customer_links:
			return
		
		from culinary_portal.woocommerce_endpoint import update_wordpress_user_from_customer
		
		for customer_name in customer_links:
			try:
				customer_doc = frappe.get_doc("Customer", customer_name)
			except frappe.DoesNotExistError:
				continue
			
			if not getattr(customer_doc, "custom_portal_user_id", None):
				continue
			
			update_wordpress_user_from_customer(customer_doc)
	
	except Exception:
		frappe.log_error(
			title="Address WordPress Sync Error",
			message=frappe.get_traceback(),
		)


def handle_customer_on_trash(doc, method=None):
	"""
	Customer silindiğinde WordPress'te user ve B2B Group'u da siler.
	Hook tarafından çağrılır.
	"""
	try:
		# Flag kontrolü - tekrar çalışmasını önle
		if getattr(doc.flags, "wp_delete_sync_ran", False):
			return
		doc.flags.wp_delete_sync_ran = True
		
		# TÜM background job'ları ve enqueue işlemlerini devre dışı bırak
		frappe.flags.in_import = True
		frappe.flags.in_test = True
		frappe.flags.enqueue_after_commit = []
		
		portal_user_id = getattr(doc, "custom_portal_user_id", None)
		b2b_group_id = getattr(doc, "custom_b2b_group_id", None)
		
		if not portal_user_id and not b2b_group_id:
			# Flag'leri geri al
			frappe.flags.in_import = False
			frappe.flags.in_test = False
			return
		
		print(f"\n\n\n DEBUG: Customer siliniyor - {doc.name}")
		print(f"\n\n\n DEBUG: Portal User ID: {portal_user_id}, B2B Group ID: {b2b_group_id}")
		
		# WordPress User'ı sil
		if portal_user_id:
			print(f"\n\n\n DEBUG: WordPress User siliniyor (ID: {portal_user_id})...")
			try:
				user_deleted = delete_wp_user(portal_user_id)
				if user_deleted:
					print(f"\n\n\n DEBUG: WordPress User başarıyla silindi")
				else:
					print(f"\n\n\n DEBUG: WordPress User silinemedi!")
			except Exception as e:
				print(f"\n\n\n DEBUG: WordPress User silme hatası: {str(e)}")
				frappe.log_error(
					title="WordPress User Delete Error",
					message=f"Customer: {doc.name}\nError: {str(e)}",
				)
		
		# B2B Group'u sil
		if b2b_group_id:
			print(f"\n\n\n DEBUG: B2B Group siliniyor (ID: {b2b_group_id})...")
			try:
				group_deleted = delete_b2b_group(b2b_group_id)
				if group_deleted:
					print(f"\n\n\n DEBUG: B2B Group başarıyla silindi")
				else:
					print(f"\n\n\n DEBUG: B2B Group silinemedi!")
			except Exception as e:
				print(f"\n\n\n DEBUG: B2B Group silme hatası: {str(e)}")
				frappe.log_error(
					title="WordPress B2B Group Delete Error",
					message=f"Customer: {doc.name}\nError: {str(e)}",
				)
		
		# Flag'leri geri al
		frappe.flags.in_import = False
		frappe.flags.in_test = False
			
	except Exception as e:
		print(f"\n\n\n DEBUG: Customer on_trash exception: {str(e)}")
		frappe.log_error(
			title="Customer On Trash Error",
			message=frappe.get_traceback(),
		)
		# Hata olsa bile flag'leri geri al
		frappe.flags.in_import = False
		frappe.flags.in_test = False


@frappe.whitelist()
def create_b2b_group_for_customer(customer_name):
    """
    Frappe whitelist function - Can be called from client side.
    Creates B2B Group for Customer.
    """
    try:
        if not customer_name:
            return {
                "status": "error",
                "message": frappe._("Customer name not found")
            }
        
        group_id = create_b2b_group(customer_name)
        
        if group_id:
            return {
                "status": "success",
                "message": frappe._("B2B Group created successfully"),
                "group_id": group_id
            }
        else:
            return {
                "status": "error",
                "message": frappe._("Failed to create B2B Group")
            }
            
    except Exception as e:
        frappe.log_error(
            title="Create B2B Group API Error",
            message=frappe.get_traceback()
        )
        return {
            "status": "error",
            "message": frappe._("Error: {0}").format(str(e))
        }

