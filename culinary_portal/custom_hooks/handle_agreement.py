import frappe
import requests

from culinary_portal.custom_hooks.create_item import (
    get_wo_url,
    get_wp_user,
    get_wp_app_key,
    get_vendor_category_id
)


def handle_agreement_before_submit(doc, method=None):
	"""
	Agreement submit edilmeden önce custom_customer_note alanının doldurulmasını kontrol eder.
	Eğer alan boşsa, JavaScript tarafında modal açılması için flag set edilir.
	"""
	# JavaScript tarafında modal açılacak, burada sadece kontrol yapıyoruz
	if not doc.custom_customer_note:
		# JavaScript tarafında modal açılacak, burada sadece flag set ediyoruz
		doc.flags.show_customer_note_modal = True


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
        
        # Vendor ana kategori ID'sini dinamik olarak ekle
        vendor_cat_id = get_vendor_category_id()
        if not vendor_cat_id:
            frappe.throw(frappe._("Lütfen 'Vendor' ürün grubunu oluşturun ve WooCommerce kategori ID'sini tanımlayın"))
        
        vendor_cat_id_str = str(vendor_cat_id)
        if vendor_cat_id_str not in unique_wc_category_ids:
            unique_wc_category_ids.append(vendor_cat_id_str)
        
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
        
        # Agreement submit edildiğinde oluşturulan Item Price'ları WordPress'e senkronize et
        if hasattr(doc, 'customer') and doc.customer and hasattr(doc, 'agreement_items') and doc.agreement_items:
            print(f"\n\n\n=== Agreement Submit - Item Price Sync Başladı ===")
            print(f"Agreement: {doc.name}")
            print(f"Customer: {doc.customer}")
            
            # Agreement'ın customer'ı price_list adı olarak kullanılıyor
            price_list_name = doc.customer
            
            # Agreement items'daki item'ları topla
            item_codes = []
            for item in doc.agreement_items:
                if hasattr(item, 'item_code') and item.item_code:
                    item_codes.append(item.item_code)
            
            print(f"Agreement items'daki item sayısı: {len(item_codes)}")
            
            if item_codes:
                # Bu item'lar için Item Price'ları bul
                item_prices = frappe.db.get_list(
                    "Item Price",
                    filters={
                        "price_list": price_list_name,
                        "item_code": ["in", item_codes],
                    },
                    fields=["name", "item_code"],
                    limit_page_length=0,
                )
                
                print(f"Bulunan Item Price sayısı: {len(item_prices)}")
                
                # Her Item Price için WordPress'e senkronize et
                synced_items = set()
                for item_price in item_prices:
                    item_code = item_price.get("item_code")
                    item_price_name = item_price.get("name")
                    
                    # Aynı item için birden fazla Item Price varsa sadece bir kez sync et
                    if item_code and item_code not in synced_items:
                        try:
                            print(f"Item Price sync ediliyor: {item_price_name} (Item: {item_code})")
                            # Queue'ya ekle
                            frappe.enqueue(
                                "culinary_portal.custom_hooks.create_item.sync_item_to_woocommerce",
                                doctype="Item Price",
                                docname=item_price_name,
                                skip_price_update=False,
                                queue="default",
                                timeout=300,
                                now=False,
                            )
                            synced_items.add(item_code)
                            print(f"✅ Item Price {item_price_name} queue'ya eklendi")
                        except Exception as e:
                            print(f"❌ Item Price {item_price_name} sync hatası: {str(e)}")
                            frappe.log_error(
                                title=f"Agreement Item Price Sync Error - {item_price_name}",
                                message=f"Item Price: {item_price_name}\nItem: {item_code}\n{frappe.get_traceback()}"
                            )
                
                print(f"Toplam {len(synced_items)} item WordPress'e senkronize edilecek")
            else:
                print("Agreement items'da item bulunamadı")
            
            print(f"=== Agreement Submit - Item Price Sync Bitti ===\n\n\n")
        
    except Exception:
        frappe.log_error(
            title="Agreement Item Groups Print Error",
            message=frappe.get_traceback()
        )


def handle_agreement_cancelled(doc, method=None):
    """
    Agreement cancel olduğunda:
    1. Status'u "Cancelled" olarak günceller
    2. Category'lerin B2B King visibility'sini kapatır (0 yapar).
    """
    frappe.throw("CICD TEST")
    try:
        # Status'u "Cancelled" olarak güncelle
        doc.db_set("status", "Cancelled", update_modified=False)
        
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
        
        # NOT: Cancel işleminde Vendor parent category eklenmez
        # Sadece agreement'taki spesifik kategoriler kapatılır
        
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
        
        print(f"\n\n\n=== Agreement Cancelled - Disabling Categories ===")
        print(f"Agreement: {doc.name}")
        print(f"Customer: {getattr(doc, 'customer', 'N/A')}")
        print(f"Customer B2B Group ID: {customer_b2b_group_id}")
        print(f"Supplier: {getattr(doc, 'supplier', 'N/A')}")
        print(f"WC Category IDs to Disable: {unique_wc_category_ids}")
        print(f"Unique Category Count: {len(unique_wc_category_ids)}")
        print(f"===========================\n\n\n")
        
        # WooCommerce'e category meta update işlemi (visibility'yi kapat)
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
                            meta_field_name: ["0"]  # Visibility'yi kapat
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
                        print(f"✅ Category {wc_category_id} disabled successfully")
                    else:
                        error_count += 1
                        print(f"❌ Category {wc_category_id} failed: {resp.status_code} - {resp.text}")
                        frappe.log_error(
                            title=f"Agreement Cancel Category Meta Update Error - {wc_category_id}",
                            message=f"Status: {resp.status_code}\nResponse: {resp.text}"
                        )
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Exception for Category {wc_category_id}: {str(e)}")
                    frappe.log_error(
                        title=f"Agreement Cancel Category Meta Update Exception - {wc_category_id}",
                        message=frappe.get_traceback()
                    )
            
            print(f"\n=== Disable Results ===")
            print(f"Success: {success_count}/{len(unique_wc_category_ids)}")
            print(f"Errors: {error_count}/{len(unique_wc_category_ids)}")
            print(f"======================\n\n\n")
        
    except Exception:
        frappe.log_error(
            title="Agreement Cancel Category Disable Error",
            message=frappe.get_traceback()
        )


