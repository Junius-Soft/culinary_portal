import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def register_customer(email, first_name, last_name, phone, password, reference_code=None, company_name=None):
    """Custom kayıt - API Key gerekmez"""
    
    try:
        if frappe.db.exists("User", email):
            frappe.throw(_("Bu e-posta adresi zaten kayıtlı"))
        
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "mobile_no": phone,
            "enabled": 1,
            "new_password": password,
            "send_welcome_email": 0,
            "user_type": "Website User",
        })
        
        if reference_code:
            user.reference_code = reference_code
        if company_name:
            user.company_name = company_name
        
        # Background job'ları devre dışı bırak (RQ hata önleme)
        user.flags.ignore_permissions = True
        user.flags.ignore_mandatory = True
        user.flags.ignore_links = True
        
        # Background job tetiklenmesini engelle
        frappe.flags.in_import = True
        frappe.flags.in_test = True
        
        user.insert(ignore_permissions=True)
        user.add_roles("Customer")
        
        # Flag'leri geri al
        frappe.flags.in_import = False
        frappe.flags.in_test = False
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Kayıt başarılı!",
            "user": {"email": user.email, "full_name": user.full_name}
        }
        
    except Exception as e:
        # Hata durumunda flag'leri geri al
        frappe.flags.in_import = False
        frappe.flags.in_test = False
        
        frappe.log_error(f"Registration error: {str(e)}")
        frappe.throw(_("Kayıt başarısız: {0}").format(str(e)))