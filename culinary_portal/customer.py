import frappe
import json
@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_customer_from_restaurant():
    """
    Restaurant Registration formundan gelen verilerle Customer, Address ve Contact oluşturur.
    """
    try:
        if frappe.request.method != 'POST':
            return {"success": False, "error": "Method not allowed"}
        # JSON verisini al
        data = None
        try:
            data = frappe.request.get_json()
        except:
            pass
        if not data:
            data = frappe.form_dict
        if data and hasattr(data, 'items'):
            data = dict(data)
        if not data:
            return {"success": False, "error": "No data received"}
        # Debug log
        frappe.log_error(
            title="Restaurant Customer Webhook",
            message=f"Data: {json.dumps(data, indent=2, default=str)}"
        )
        # Zorunlu alanlar
        company_name = data.get('text_2', '').strip()
        email = data.get('email_1', '').strip()
        if not company_name:
            return {"success": False, "error": "Company name required"}
        if not email:
            return {"success": False, "error": "Email required"}
        # Duplicate kontrolü
        existing = frappe.db.get_value("Customer", {"email_id": email}, "name")
        if existing:
            return {"success": True, "message": "Customer exists", "customer_name": existing}
        # Address parse
        address_data = {}
        if data.get('address_1') and isinstance(data.get('address_1'), str):
            try:
                address_data = json.loads(data.get('address_1'))
            except:
                pass
        if not address_data and data.get('address_1_street_address'):
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
            "custom_portal_email": email,
            "mobile_no": data.get('phone_1', ''),
            "tax_id": data.get('text_3', ''),
            "custom_company_type": data.get('select_1', ''),
            "custom_ust_id": data.get('text_4', ''),
        })
        customer_doc.insert(ignore_permissions=True)
        # Address oluştur
        address_doc = None
        if address_data.get('street_address') or address_data.get('city'):
            country_value = data.get('select_2', 'Germany')
            if not frappe.db.exists("Country", country_value):
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
        # Contact oluştur
        contact_doc = None
        firmen_name = data.get('text_7', '').strip()
        firmen_mail = data.get('email_2', '').strip()
        firmen_phone = data.get('phone_2', '').strip()
        if firmen_name and firmen_mail:
            contact_doc = frappe.get_doc({
                "doctype": "Contact",
                "first_name": firmen_name,
                "email_ids": [{"email_id": firmen_mail, "is_primary": 1}],
                "phone_nos": ([{"phone": firmen_phone, "is_primary_phone": 1}] if firmen_phone else []),
                "links": [{"link_doctype": "Customer", "link_name": customer_doc.name}],
            })
            contact_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {
            "success": True,
            "message": "Customer created successfully",
            "customer_name": customer_doc.name,
            "address_name": address_doc.name if address_doc else None,
            "contact_name": contact_doc.name if contact_doc else None
        }
    except Exception as e:
        frappe.log_error(
            title="Customer Creation Error",
            message=f"Error: {str(e)}\n{frappe.get_traceback()}"
        )
        frappe.db.rollback()
        return {"success": False, "error": str(e)}