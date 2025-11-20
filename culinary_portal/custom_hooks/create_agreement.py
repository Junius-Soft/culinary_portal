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
	print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER BAŞLADI ==========")
	print(f"\n\n\n DEBUG-AGREEMENT-1 Customer: {doc.name}")
	print(f"\n\n\n DEBUG-AGREEMENT-2 __islocal: {doc.get('__islocal')}")
	
	try:
		# WordPress sync'ten gelen update'leri atla
		if getattr(doc.flags, "skip_wordpress_sync", False):
			print("\n\n\n DEBUG-AGREEMENT-3 WordPress sync flag var, hook atlanıyor")
			return
		
		# Yeni değerler
		new_vendors = {
			1: getattr(doc, "custom_brand_vendor_1", "") or "",
			2: getattr(doc, "custom_brand_vendor_2", "") or "",
			3: getattr(doc, "custom_brand_vendor_3", "") or "",
		}
		
		print(f"\n\n\n DEBUG-AGREEMENT-4 Yeni vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{new_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{new_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{new_vendors[3]}'")
		
		# Yeni customer kontrolü before_save'de yapılmaz, after_insert'te yapılacak
		if doc.get("__islocal"):
			print("\n\n\n DEBUG-AGREEMENT-5 Yeni customer (insert) - before_save'de atlanıyor, after_insert'te işlenecek")
			print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER BİTTİ (YENİ - AFTER_INSERT'E BIRAKILDI) ==========")
			return
		
		# Mevcut customer için değişiklik kontrolü
		print("\n\n\n DEBUG-AGREEMENT-9 Mevcut customer (update)")
		
		# before_save hook'unda has_value_changed() çalışır
		has_vendor_changes = (
			doc.has_value_changed("custom_brand_vendor_1") or
			doc.has_value_changed("custom_brand_vendor_2") or
			doc.has_value_changed("custom_brand_vendor_3")
		)
		
		print(f"\n\n\n DEBUG-AGREEMENT-10 has_value_changed kontrolü:")
		print(f"  custom_brand_vendor_1: {doc.has_value_changed('custom_brand_vendor_1')}")
		print(f"  custom_brand_vendor_2: {doc.has_value_changed('custom_brand_vendor_2')}")
		print(f"  custom_brand_vendor_3: {doc.has_value_changed('custom_brand_vendor_3')}")
		print(f"  Toplam değişiklik var mı: {has_vendor_changes}")
		
		if not has_vendor_changes:
			print("\n\n\n DEBUG-AGREEMENT-11 Değişiklik yok (has_value_changed), çıkılıyor")
			print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER BİTTİ (DEĞİŞİKLİK YOK) ==========")
			return
		
		# Değişiklik var, eski değerleri DB'den al (before_save'de DB henüz güncellenmemiş)
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
		
		print(f"\n\n\n DEBUG-AGREEMENT-11.1 DB'den eski değerler alındı: {old_values}")
		
		if not old_values:
			# Yeni customer ise, tüm vendor'lar için kontrol et
			print("\n\n\n DEBUG-AGREEMENT-11.2 Eski değerler bulunamadı (yeni customer?), tüm vendor'lar için kontrol ediliyor")
			old_vendors = {1: "", 2: "", 3: ""}
		else:
			old_vendors = {
				1: old_values.get("custom_brand_vendor_1", "") or "",
				2: old_values.get("custom_brand_vendor_2", "") or "",
				3: old_values.get("custom_brand_vendor_3", "") or "",
			}
		
		print(f"\n\n\n DEBUG-AGREEMENT-12 Eski vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{old_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{old_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{old_vendors[3]}'")
		
		print(f"\n\n\n DEBUG-AGREEMENT-12 Eski vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{old_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{old_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{old_vendors[3]}'")
		
		# Değişiklik var mı kontrol et
		has_changes = False
		for idx in [1, 2, 3]:
			if new_vendors[idx] != old_vendors[idx]:
				has_changes = True
				print(f"\n\n\n DEBUG-AGREEMENT-13 Değişiklik bulundu! Vendor {idx}: '{old_vendors[idx]}' -> '{new_vendors[idx]}'")
				break
		
		if not has_changes:
			print("\n\n\n DEBUG-AGREEMENT-14 Değişiklik yok, çıkılıyor")
			print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER BİTTİ (DEĞİŞİKLİK YOK) ==========")
			return
		
		# Değişiklik varsa, yeni vendor'lar için agreement oluştur
		for idx in [1, 2, 3]:
			new_supplier = new_vendors[idx]
			old_supplier = old_vendors[idx]
			
			print(f"\n\n\n DEBUG-AGREEMENT-15 Vendor {idx} kontrolü:")
			print(f"  Eski: '{old_supplier}'")
			print(f"  Yeni: '{new_supplier}'")
			
			# Yeni supplier eklendi veya değişti
			if new_supplier and new_supplier != old_supplier:
				print(f"\n\n\n DEBUG-AGREEMENT-16 Yeni supplier eklendi/değişti: {new_supplier}")
				# Supplier var mı kontrol et
				if frappe.db.exists("Supplier", new_supplier):
					print(f"\n\n\n DEBUG-AGREEMENT-17 Supplier mevcut: {new_supplier}")
					# Bu customer-supplier için zaten agreement var mı kontrol et
					existing_agreement = frappe.db.exists(
						"Agreement",
						{
							"customer": doc.name,
							"supplier": new_supplier,
							"docstatus": ["!=", 2]  # Cancel edilmemiş
						}
					)
					
					print(f"\n\n\n DEBUG-AGREEMENT-18 Mevcut agreement kontrolü: {existing_agreement}")
					
					# Agreement yoksa oluştur
					if not existing_agreement:
						print(f"\n\n\n DEBUG-AGREEMENT-19 Agreement oluşturuluyor: Customer={doc.name}, Supplier={new_supplier}")
						_create_agreement(doc.name, new_supplier)
					else:
						print(f"\n\n\n DEBUG-AGREEMENT-20 Agreement zaten mevcut, atlanıyor")
				else:
					print(f"\n\n\n DEBUG-AGREEMENT-21 Supplier mevcut değil: {new_supplier}")
			else:
				print(f"\n\n\n DEBUG-AGREEMENT-22 Vendor {idx} değişmedi veya boş")
		
		print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER BİTTİ ==========")
		
	except Exception as e:
		print(f"\n\n\n DEBUG-AGREEMENT-ERROR Exception: {str(e)}")
		print(f"\n\n\n DEBUG-AGREEMENT-ERROR Traceback: {frappe.get_traceback()}")
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
	print(f"\n\n\n ========== _CREATE_AGREEMENT BAŞLADI ==========")
	print(f"\n\n\n DEBUG-AGREEMENT-CREATE-1 Customer: {customer_name}, Supplier: {supplier_name}")
	
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
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-2 Mevcut agreement kontrolü: {existing}")
		
		if existing:
			print(f"\n\n\n DEBUG-AGREEMENT-CREATE-3 Agreement zaten mevcut, çıkılıyor")
			return
		
		# Tarihleri hesapla
		valid_from = today()
		valid_to = add_years(valid_from, 3)
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-4 Tarihler: valid_from={valid_from}, valid_to={valid_to}")
		
		# Agreement oluştur
		agreement_doc = frappe.new_doc("Agreement")
		agreement_doc.customer = customer_name
		agreement_doc.supplier = supplier_name
		agreement_doc.valid_from = valid_from
		agreement_doc.valid_to = valid_to
		agreement_doc.discount_rate = 20
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-5 Agreement doc oluşturuldu")
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-6 Supplier seçildi, otomatik item'lar eklenecek")
		
		# Agreement items zorunlu olduğu için validation'ı bypass et
		# Supplier seçildiğinde otomatik olarak o supplier'a ait ürünler eklenecek
		agreement_doc.flags.ignore_permissions = True
		agreement_doc.flags.ignore_validate = True
		agreement_doc.flags.ignore_mandatory = True
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-7 Agreement insert ediliyor (validation bypass)...")
		agreement_doc.insert(ignore_permissions=True)
		
		# Agreement oluşturulduktan sonra supplier'a ait ürünler otomatik eklenecek
		# Bu yüzden hiçbir item eklemiyoruz
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-8 Agreement insert edildi, supplier'a ait ürünler otomatik eklenecek")
		
		frappe.db.commit()
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-10 Agreement başarıyla oluşturuldu: {agreement_doc.name}")
		print(f"\n\n\n ========== _CREATE_AGREEMENT BİTTİ ==========")
		
		frappe.logger().info(
			f"Agreement oluşturuldu: Customer={customer_name}, Supplier={supplier_name}, Name={agreement_doc.name}"
		)
		
	except Exception as e:
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-ERROR Exception: {str(e)}")
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-ERROR Traceback: {frappe.get_traceback()}")
		frappe.log_error(
			title="Agreement Creation Error",
			message=f"Customer: {customer_name}, Supplier: {supplier_name}\n{frappe.get_traceback()}"
		)


def create_agreements_for_customer_after_insert(doc, method=None):
	"""
	Yeni Customer insert edildikten sonra brand vendor alanlarına göre Agreement oluşturur.
	"""
	print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER AFTER INSERT BAŞLADI ==========")
	print(f"\n\n\n DEBUG-AGREEMENT-AI-1 Customer: {doc.name}")
	
	try:
		# WordPress sync'ten gelen insert'leri atla
		if getattr(doc.flags, "skip_wordpress_sync", False):
			print("\n\n\n DEBUG-AGREEMENT-AI-2 WordPress sync flag var, hook atlanıyor")
			return
		
		# Yeni vendor değerleri
		new_vendors = {
			1: getattr(doc, "custom_brand_vendor_1", "") or "",
			2: getattr(doc, "custom_brand_vendor_2", "") or "",
			3: getattr(doc, "custom_brand_vendor_3", "") or "",
		}
		
		print(f"\n\n\n DEBUG-AGREEMENT-AI-3 Yeni vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{new_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{new_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{new_vendors[3]}'")
		
		# Boş olmayan vendor'lar için agreement oluştur
		for idx, supplier in enumerate([new_vendors[1], new_vendors[2], new_vendors[3]], start=1):
			if supplier:
				print(f"\n\n\n DEBUG-AGREEMENT-AI-4 Vendor {idx} bulundu: {supplier}")
				if frappe.db.exists("Supplier", supplier):
					print(f"\n\n\n DEBUG-AGREEMENT-AI-5 Supplier mevcut, agreement oluşturuluyor")
					_create_agreement(doc.name, supplier)
				else:
					print(f"\n\n\n DEBUG-AGREEMENT-AI-6 Supplier mevcut değil: {supplier}")
		
		print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER AFTER INSERT BİTTİ ==========")
		
	except Exception as e:
		print(f"\n\n\n DEBUG-AGREEMENT-AI-ERROR Exception: {str(e)}")
		print(f"\n\n\n DEBUG-AGREEMENT-AI-ERROR Traceback: {frappe.get_traceback()}")
		frappe.log_error(
			title="Customer Agreement Creation After Insert Error",
			message=frappe.get_traceback()
		)

