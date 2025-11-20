import frappe
from frappe.utils import today, add_years, getdate
from datetime import date


def create_agreements_for_customer(doc, method=None):
	"""
	Customer save olduğunda custom_brand_vendor alanlarına göre Agreement oluşturur.
	
	Her bir custom_brand_vendor_X için bir Agreement kaydı oluşturur:
	- customer: customer_name
	- supplier: custom_brand_vendor_X
	- valid_from: bugünün tarihi
	- valid_to: 3 yıl sonrası
	- discount_rate: 20
	
	Sadece custom_brand_vendor alanlarında değişiklik varsa yeni agreement oluşturur.
	"""
	try:
		# Flag kontrolü - tekrar çalışmasını önle
		if getattr(doc.flags, "culinary_agreement_creation_ran", False):
			return
		doc.flags.culinary_agreement_creation_ran = True
		
		# Yeni customer ise (insert) ve brand vendor alanları doluysa
		if doc.get("__islocal"):
			# Yeni customer için brand vendor alanlarını kontrol et
			brand_vendors = [
				getattr(doc, "custom_brand_vendor_1", "") or "",
				getattr(doc, "custom_brand_vendor_2", "") or "",
				getattr(doc, "custom_brand_vendor_3", "") or "",
			]
			
			# Boş olmayan vendor'lar için agreement oluştur
			for idx, supplier in enumerate(brand_vendors, start=1):
				if supplier and frappe.db.exists("Supplier", supplier):
					_create_agreement(doc.name, supplier)
			return
		
		# Mevcut customer için değişiklik kontrolü
		old_values = frappe.db.get_value(
			"Customer",
			doc.name,
			[
				"custom_brand_vendor_1",
				"custom_brand_vendor_2",
				"custom_brand_vendor_3"
			],
			as_dict=True
		)
		
		if not old_values:
			return
		
		# Yeni değerler
		new_vendors = {
			1: getattr(doc, "custom_brand_vendor_1", "") or "",
			2: getattr(doc, "custom_brand_vendor_2", "") or "",
			3: getattr(doc, "custom_brand_vendor_3", "") or "",
		}
		
		# Eski değerler
		old_vendors = {
			1: old_values.get("custom_brand_vendor_1", "") or "",
			2: old_values.get("custom_brand_vendor_2", "") or "",
			3: old_values.get("custom_brand_vendor_3", "") or "",
		}
		
		# Değişiklik var mı kontrol et
		has_changes = False
		for idx in [1, 2, 3]:
			if new_vendors[idx] != old_vendors[idx]:
				has_changes = True
				break
		
		if not has_changes:
			return
		
		# Değişiklik varsa, yeni vendor'lar için agreement oluştur
		for idx in [1, 2, 3]:
			new_supplier = new_vendors[idx]
			old_supplier = old_vendors[idx]
			
			# Yeni supplier eklendi veya değişti
			if new_supplier and new_supplier != old_supplier:
				# Supplier var mı kontrol et
				if frappe.db.exists("Supplier", new_supplier):
					# Bu customer-supplier için zaten agreement var mı kontrol et
					existing_agreement = frappe.db.exists(
						"Agreement",
						{
							"customer": doc.name,
							"supplier": new_supplier,
							"docstatus": ["!=", 2]  # Cancel edilmemiş
						}
					)
					
					# Agreement yoksa oluştur
					if not existing_agreement:
						_create_agreement(doc.name, new_supplier)
		
	except Exception:
		frappe.log_error(
			title="Customer Agreement Creation Error",
			message=frappe.get_traceback()
		)


def _create_agreement(customer_name, supplier_name):
	"""
	Agreement oluşturur.
	
	Args:
		customer_name: Customer name
		supplier_name: Supplier name
	"""
	try:
		# Agreement zaten var mı kontrol et
		existing = frappe.db.exists(
			"Agreement",
			{
				"customer": customer_name,
				"supplier": supplier_name,
				"docstatus": ["!=", 2]  # Cancel edilmemiş
			}
		)
		
		if existing:
			return
		
		# Tarihleri hesapla
		valid_from = today()
		valid_to = add_years(valid_from, 3)
		
		# Agreement oluştur
		agreement_doc = frappe.new_doc("Agreement")
		agreement_doc.customer = customer_name
		agreement_doc.supplier = supplier_name
		agreement_doc.valid_from = valid_from
		agreement_doc.valid_to = valid_to
		agreement_doc.discount_rate = 20
		
		# Agreement items zorunlu olduğu için dummy item ekle
		# En az bir item bulmaya çalış
		item = frappe.db.get_value("Item", {"disabled": 0}, "name")
		
		if item:
			agreement_doc.append("agreement_items", {
				"item_code": item,
				"price_list_rate": 0.01  # Minimum değer
			})
		else:
			# Item yoksa validation'ı bypass et
			agreement_doc.flags.ignore_validate = True
			agreement_doc.flags.ignore_mandatory = True
		
		agreement_doc.flags.ignore_permissions = True
		agreement_doc.insert(ignore_permissions=True)
		frappe.db.commit()
		
		frappe.logger().info(
			f"Agreement oluşturuldu: Customer={customer_name}, Supplier={supplier_name}"
		)
		
	except Exception:
		frappe.log_error(
			title="Agreement Creation Error",
			message=f"Customer: {customer_name}, Supplier: {supplier_name}\n{frappe.get_traceback()}"
		)

