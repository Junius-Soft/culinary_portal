import frappe
import requests

from culinary_portal.custom_hooks.create_item import (
    get_wo_url,
    get_wp_user,
    get_wp_app_key
)


def handle_agreement_saved(doc, method=None):
    """
    Agreement save olduğunda alt tablodaki (agreement_items) 
    ürünlerin item_group'larını ve WooCommerce category ID'lerini tuple olarak console'a yazdırır.
    """
    try:
        # agreement_items içinden benzersiz WC category ID'lerini topla
        unique_wc_category_ids = []
        seen_item_groups = set()
        
        if hasattr(doc, 'agreement_items') and doc.agreement_items:
            for item in doc.agreement_items:
                if hasattr(item, 'item_group') and item.item_group:
                    item_group_name = item.item_group
                    # İlk görüleni koru
                    if item_group_name not in seen_item_groups:
                        seen_item_groups.add(item_group_name)
                        wc_category_id = frappe.db.get_value(
                            "Item Group",
                            item_group_name,
                            "custom_woocommerce_category_id"
                        )
                        if wc_category_id:
                            unique_wc_category_ids.append(wc_category_id)
        
        # Default parent category ID'sini ekle (303)
        if '303' not in unique_wc_category_ids:
            unique_wc_category_ids.append('303')
        
        # Supplier'ın WC category ID'sini ekle
        if hasattr(doc, 'supplier') and doc.supplier:
            supplier_wc_category_id = frappe.db.get_value(
                "Supplier",
                doc.supplier,
                "custom_woocommerce_category_id"
            )
            if supplier_wc_category_id and supplier_wc_category_id not in unique_wc_category_ids:
                unique_wc_category_ids.append(supplier_wc_category_id)
        
        # Customer'ın B2B Group ID'sini al
        customer_b2b_group_id = None
        if hasattr(doc, 'customer') and doc.customer:
            customer_b2b_group_id = frappe.db.get_value(
                "Customer",
                doc.customer,
                "custom_b2b_group_id"
            )
        
        print(f"\n\n\n=== Agreement Data ===")
        print(f"Agreement: {doc.name}")
        print(f"Customer: {getattr(doc, 'customer', 'N/A')}")
        print(f"Customer B2B Group ID: {customer_b2b_group_id}")
        print(f"Supplier: {getattr(doc, 'supplier', 'N/A')}")
        print(f"WC Category IDs: {unique_wc_category_ids}")
        print(f"Unique Category Count: {len(unique_wc_category_ids)}")
        print(f"===========================\n\n\n")
        
        # WooCommerce'e category meta update işlemi
        if customer_b2b_group_id and unique_wc_category_ids:
            base_url = get_wo_url()
            wp_user = get_wp_user()
            wp_app_key = get_wp_app_key()
            
            # Dinamik meta field adı
            meta_field_name = f"b2bking_group_{customer_b2b_group_id}"
            
            success_count = 0
            error_count = 0
            
            for wc_category_id in unique_wc_category_ids:
                try:
                    url = f"{base_url}/wp-json/wp/v2/product_cat/{wc_category_id}"
                    
                    payload = {
                        "meta": {
                            meta_field_name: ["1"]
                        }
                    }
                    
                    resp = requests.put(
                        url,
                        auth=(wp_user, wp_app_key),
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=40
                    )
                    
                    if resp.status_code in (200, 201):
                        success_count += 1
                        print(f"✅ Category {wc_category_id} updated successfully")
                    else:
                        error_count += 1
                        print(f"❌ Category {wc_category_id} failed: {resp.status_code} - {resp.text}")
                        frappe.log_error(
                            title=f"Agreement Category Meta Update Error - {wc_category_id}",
                            message=f"Status: {resp.status_code}\nResponse: {resp.text}"
                        )
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Exception for Category {wc_category_id}: {str(e)}")
                    frappe.log_error(
                        title=f"Agreement Category Meta Update Exception - {wc_category_id}",
                        message=frappe.get_traceback()
                    )
            
            print(f"\n=== Update Results ===")
            print(f"Success: {success_count}/{len(unique_wc_category_ids)}")
            print(f"Errors: {error_count}/{len(unique_wc_category_ids)}")
            print(f"======================\n\n\n")
        
    except Exception:
        frappe.log_error(
            title="Agreement Item Groups Print Error",
            message=frappe.get_traceback()
        )


