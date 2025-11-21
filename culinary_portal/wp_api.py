import frappe
@frappe.whitelist()
def create_order_from_woocommerce(payload=None, submit=0):
    """Create a Sales Order from given payload. Returns created document summary as dict.

    Minimal required: items: [{ item_code, qty }]
    Optional: company, customer, transaction_date, delivery_date, selling_price_list, taxes_and_charges, taxes
    """
    try:
        # Parse payload from arg or request body
        data = payload
        if isinstance(data, str):
            data = frappe.parse_json(data) or {}
        if not isinstance(data, dict) or not data:
            body = frappe.request.get_json(silent=True)
            data = body if isinstance(body, dict) else {}
        if not isinstance(data, dict):
            frappe.throw("Payload must be a JSON object.")

        # Resolve company
        company = data.get("company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            first_enabled = frappe.db.get_list(
                "Company",
                filters={"disabled": 0},
                fields=["name"],
                limit_page_length=1,
            )
            company = first_enabled[0]["name"] if first_enabled else None
        if not company:
            frappe.throw("No active Company found.")

        # Resolve customer
        customer_name = data.get("customer")
        if not customer_name:
            usr = frappe.session.user
            linked = frappe.get_all(
                "Customer",
                filters={"custom_user": usr},
                fields=["name"],
                limit_page_length=1,
            )
            customer_name = linked[0]["name"] if linked else None
        if not customer_name:
            frappe.throw("Customer is required or must be linked via Customer.custom_user.")

        # Items validation
        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            frappe.throw("Items list is required.")

        # Dates & options
        transaction_date = data.get("transaction_date") or frappe.utils.today()
        default_delivery = data.get("delivery_date") or transaction_date
        price_list = data.get("selling_price_list")

        # Build Sales Order
        so = frappe.new_doc("Sales Order")
        so.company = company
        so.customer = customer_name
        so.transaction_date = transaction_date
        if price_list:
            so.selling_price_list = price_list

        for row in items:
            if not isinstance(row, dict):
                frappe.throw("Each item must be an object.")
            item_code = row.get("item_code")
            qty = row.get("qty")
            if not item_code or not qty:
                frappe.throw("Item must have item_code and qty.")
            child = so.append("items", {})
            child.item_code = item_code
            child.qty = qty
            if row.get("rate") is not None:
                child.rate = row.get("rate")
            if row.get("warehouse"):
                child.warehouse = row.get("warehouse")
            child.delivery_date = row.get("delivery_date") or default_delivery

        # Taxes
        if data.get("taxes_and_charges"):
            so.taxes_and_charges = data.get("taxes_and_charges")
        if isinstance(data.get("taxes"), list):
            for tx in data.get("taxes"):
                if not isinstance(tx, dict):
                    continue
                tax_row = so.append("taxes", {})
                for k in ["charge_type", "account_head", "rate", "description"]:
                    if tx.get(k) is not None:
                        tax_row.set(k, tx.get(k))

        so.flags.ignore_mandatory = False
        so.insert()

        if int(submit) == 1:
            so.submit()

        return {
            "name": so.name,
            "docstatus": so.docstatus,
            "status": so.status,
            "company": so.company,
            "customer": so.customer,
        }
    except Exception:
        frappe.log_error(reference_doctype="Sales Order", message=frappe.get_traceback())
        frappe.throw("Failed to create Sales Order. Check error logs.")


def create_order_from_woocommerce2(payload=None, submit=0):
    """Create a Sales Order from given payload. Returns created document as dict.
    """
    pass

@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_customer_from_restaurant():
    """Restaurant Registration webhook"""
    try:
        import json
        if frappe.request.method != 'POST':
            return {"success": False, "error": "Method not allowed"}
        data = None
        try:
            data = frappe.request.get_json()
        except:
            data = frappe.form_dict
        if data and hasattr(data, 'items'):
            data = dict(data)
        if not data:
            return {"success": False, "error": "No data"}
        company = data.get('text_2', '').strip()
        email = data.get('email_1', '').strip()
        if not company or not email:
            return {"success": False, "error": "Missing data"}
        existing = frappe.db.get_value("Customer", {"email_id": email}, "name")
        if existing:
            return {"success": True, "customer_name": existing}
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": company,
            "customer_type": "Company",
            "customer_group": "All Customer Groups",
            "territory": "All Territories",
            "email_id": email,
            "woocommerce_identifier": email,
            "mobile_no": data.get('phone_1', ''),
        })
        customer.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "customer_name": customer.name}
    except Exception as e:
        frappe.log_error(f"Restaurant Customer Error: {str(e)}\n{frappe.get_traceback()}")
        return {"success": False, "error": str(e)}