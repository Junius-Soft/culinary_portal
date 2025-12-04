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
	print(f"\n\n\n DEBUG-AGREEMENT-1 Customer: {doc.custom_restaurant_name}")
	print(f"\n\n\n DEBUG-AGREEMENT-2 __islocal: {doc.get('__islocal')}")
	
	try:
		# Agreement oluşturma WordPress sync'ten bağımsız çalışmalı
		# skip_wordpress_sync sadece WordPress'e geri göndermeyi atlar
		
		# Yeni değerler
		new_vendors = {
			1: getattr(doc, "custom_brand_vendor_1", "") or "",
			2: getattr(doc, "custom_brand_vendor_2", "") or "",
			3: getattr(doc, "custom_brand_vendor_3", "") or "",
			4: getattr(doc, "custom_brand_vendor_4", "") or "",
			5: getattr(doc, "custom_brand_vendor_5", "") or "",
			6: getattr(doc, "custom_brand_vendor_6", "") or "",
		}
		
		print(f"\n\n\n DEBUG-AGREEMENT-4 Yeni vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{new_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{new_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{new_vendors[3]}'")
		print(f"  custom_brand_vendor_4: '{new_vendors[4]}'")
		print(f"  custom_brand_vendor_5: '{new_vendors[5]}'")
		print(f"  custom_brand_vendor_6: '{new_vendors[6]}'")
		
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
			doc.has_value_changed("custom_brand_vendor_3") or
			doc.has_value_changed("custom_brand_vendor_4") or
			doc.has_value_changed("custom_brand_vendor_5") or
			doc.has_value_changed("custom_brand_vendor_6")
		)
		
		print(f"\n\n\n DEBUG-AGREEMENT-10 has_value_changed kontrolü:")
		print(f"  custom_brand_vendor_1: {doc.has_value_changed('custom_brand_vendor_1')}")
		print(f"  custom_brand_vendor_2: {doc.has_value_changed('custom_brand_vendor_2')}")
		print(f"  custom_brand_vendor_3: {doc.has_value_changed('custom_brand_vendor_3')}")
		print(f"  custom_brand_vendor_4: {doc.has_value_changed('custom_brand_vendor_4')}")
		print(f"  custom_brand_vendor_5: {doc.has_value_changed('custom_brand_vendor_5')}")
		print(f"  custom_brand_vendor_6: {doc.has_value_changed('custom_brand_vendor_6')}")
		print(f"  Toplam değişiklik var mı: {has_vendor_changes}")
		
		if not has_vendor_changes:
			print("\n\n\n DEBUG-AGREEMENT-11 Değişiklik yok (has_value_changed), çıkılıyor")
			print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER BİTTİ (DEĞİŞİKLİK YOK) ==========")
			return
		
		# Değişiklik var, eski değerleri DB'den al (before_save'de DB henüz güncellenmemiş)
		old_values = frappe.db.get_value(
			"Customer",
			doc.custom_restaurant_name,
			[
				"custom_brand_vendor_1",
				"custom_brand_vendor_2",
				"custom_brand_vendor_3",
				"custom_brand_vendor_4",
				"custom_brand_vendor_5",
				"custom_brand_vendor_6"
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
				4: old_values.get("custom_brand_vendor_4", "") or "",
				5: old_values.get("custom_brand_vendor_5", "") or "",
				6: old_values.get("custom_brand_vendor_6", "") or "",
			}
		
		print(f"\n\n\n DEBUG-AGREEMENT-12 Eski vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{old_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{old_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{old_vendors[3]}'")
		print(f"  custom_brand_vendor_4: '{old_vendors[4]}'")
		print(f"  custom_brand_vendor_5: '{old_vendors[5]}'")
		print(f"  custom_brand_vendor_6: '{old_vendors[6]}'")
		
		print(f"\n\n\n DEBUG-AGREEMENT-12 Eski vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{old_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{old_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{old_vendors[3]}'")
		print(f"  custom_brand_vendor_4: '{old_vendors[4]}'")
		print(f"  custom_brand_vendor_5: '{old_vendors[5]}'")
		print(f"  custom_brand_vendor_6: '{old_vendors[6]}'")
		
		# Değişiklik var mı kontrol et
		has_changes = False
		for idx in [1, 2, 3, 4, 5, 6]:
			if new_vendors[idx] != old_vendors[idx]:
				has_changes = True
				print(f"\n\n\n DEBUG-AGREEMENT-13 Değişiklik bulundu! Vendor {idx}: '{old_vendors[idx]}' -> '{new_vendors[idx]}'")
				break
		
		if not has_changes:
			print("\n\n\n DEBUG-AGREEMENT-14 Değişiklik yok, çıkılıyor")
			print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER BİTTİ (DEĞİŞİKLİK YOK) ==========")
			return
		
		# Değişiklik varsa, yeni vendor'lar için agreement oluştur
		for idx in [1, 2, 3, 4, 5, 6]:
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
							"customer": doc.custom_restaurant_name,
							"supplier": new_supplier,
							"docstatus": ["!=", 2]  # Cancel edilmemiş
						}
					)
					
					print(f"\n\n\n DEBUG-AGREEMENT-18 Mevcut agreement kontrolü: {existing_agreement}")
					
					# Agreement yoksa oluştur
					if not existing_agreement:
						print(f"\n\n\n DEBUG-AGREEMENT-19 Agreement oluşturuluyor: Customer={doc.custom_restaurant_name}, Supplier={new_supplier}, Vendor Index={idx}")
						_create_agreement(doc.custom_restaurant_name, new_supplier, vendor_index=idx)
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


def _create_agreement(customer_name, supplier_name, vendor_index=None):
	"""
	Agreement oluşturur.
	
	Args:
		customer_name: Customer name
		supplier_name: Supplier name
		vendor_index: Vendor index (1, 2, veya 3) - hangi marken-vendor_X için oluşturuluyor
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
		
		# Currency'yi al (supplier'dan veya company'den)
		supplier_currency = frappe.db.get_value("Supplier", supplier_name, "default_currency")
		if not supplier_currency:
			company_currency = frappe.db.get_value("Company", {"is_group": 0}, "default_currency")
			currency = company_currency or "EUR"
		else:
			currency = supplier_currency
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-6 Supplier'a ait ürünler alınıyor (currency: {currency})...")
		
		# Supplier'a ait ürünleri direkt SQL ile al (permission kontrolü olmadan)
		items = frappe.db.sql(
			"""
			select i.name as item_code, i.item_name, i.item_group,
			       i.is_kitchen_item as kitchen_item,
			       i.stock_uom as uom
			from `tabItem` i
			join `tabItem Supplier` s on s.parent = i.name and s.supplier = %s
			where i.disabled = 0 and i.is_sales_item = 1
			order by i.item_name
			""",
			supplier_name,
			as_dict=True,
		)
		
		if not items:
			print(f"\n\n\n DEBUG-AGREEMENT-CREATE-6.1 Supplier'a ait ürün bulunamadı")
			supplier_items = []
		else:
			# Standard Selling fiyatlarını al
			item_codes = [it.item_code for it in items]
			placeholders = ",".join(["%s"] * len(item_codes))
			price_rows = []
			if item_codes:
				price_rows = frappe.db.sql(
					f"""
					select item_code, price_list_rate
					from `tabItem Price`
					where price_list = 'Standard Selling' and selling = 1
					  and currency = %s and item_code in ({placeholders})
					""",
					[currency, *item_codes],
					as_dict=True,
				)
			
			price_map = {r.item_code: float(r.price_list_rate) for r in price_rows}
			
			# Eksik fiyatlar için alternatif price list'lerden fiyat al
			supplier_items = []
			for it in items:
				std_rate = price_map.get(it.item_code, 0.0)
				if not std_rate:
					# Standard Selling'de yoksa, diğer selling price list'lerden al
					alt_price = frappe.db.sql(
						"""
						select price_list_rate from `tabItem Price`
						where item_code=%s and selling=1
						  and (currency=%s or %s is null)
						order by (valid_from is null), valid_from desc, modified desc
						limit 1
						""",
						(it.item_code, currency, currency),
						as_dict=True,
					)
					if alt_price:
						std_rate = float(alt_price[0].price_list_rate)
				
				supplier_items.append({
					"item_code": it.item_code,
					"item_name": it.item_name,
					"item_group": it.item_group,
					"kitchen_item": int(it.kitchen_item or 0),
					"uom": it.uom,
					"standard_selling_rate": std_rate,
					"price_list_rate": std_rate,
					"currency": currency,
				})
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-7 {len(supplier_items)} ürün bulundu")
		
		# Discount rate'i al (20 olarak set edilmiş)
		discount_rate = frappe.utils.flt(agreement_doc.discount_rate or 20)
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-7.1 Discount rate: {discount_rate}%")
		
		# Her ürünü Agreement Items'a ekle
		for item_data in supplier_items:
			standard_selling_rate = frappe.utils.flt(item_data.get("standard_selling_rate", 0))
			
			# price_list_rate = standard_selling_rate * (1 - discount_rate / 100)
			if discount_rate and standard_selling_rate:
				price_list_rate = standard_selling_rate * (1.0 - (discount_rate / 100.0))
			else:
				price_list_rate = standard_selling_rate
			
			print(f"\n\n\n DEBUG-AGREEMENT-CREATE-7.2 Item: {item_data.get('item_code')}, Standard: {standard_selling_rate}, Discount: {discount_rate}%, Final: {price_list_rate}")
			
			agreement_doc.append("agreement_items", {
				"item_code": item_data.get("item_code"),
				"item_name": item_data.get("item_name"),
				"item_group": item_data.get("item_group"),
				"kitchen_item": item_data.get("kitchen_item", 0),
				"uom": item_data.get("uom"),
				"standard_selling_rate": standard_selling_rate,
				"price_list_rate": price_list_rate,
				"currency": item_data.get("currency", currency)
			})
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-8 {len(agreement_doc.agreement_items)} ürün Agreement Items'a eklendi")
		
		# Services değerlerini ekle (vendor_index varsa, 1-6)
		if vendor_index and vendor_index in [1, 2, 3, 4, 5, 6]:
			# Customer'dan ilgili services değerini al
			customer_doc = frappe.get_doc("Customer", customer_name)
			services_field = f"custom_brands_{vendor_index}"
			services_value = getattr(customer_doc, services_field, "") or ""
			
			print(f"\n\n\n DEBUG-AGREEMENT-CREATE-8.1 Services field: {services_field}, Value: {services_value}")
			
			if services_value:
				# Virgülle ayrılmış değerleri al
				services_list = [s.strip() for s in services_value.split(",") if s.strip()]
				
				print(f"\n\n\n DEBUG-AGREEMENT-CREATE-8.2 {len(services_list)} service bulundu: {services_list}")
				
				# Her bir service'i Agreement Services table'ına ekle
				for service in services_list:
					agreement_doc.append("custom_services", {
						"service": service
					})
					print(f"\n\n\n DEBUG-AGREEMENT-CREATE-8.3 Service eklendi: {service}")
				
				print(f"\n\n\n DEBUG-AGREEMENT-CREATE-8.4 Toplam {len(agreement_doc.custom_services)} service eklendi")
			else:
				print(f"\n\n\n DEBUG-AGREEMENT-CREATE-8.5 Services değeri boş, atlanıyor")
		
		agreement_doc.flags.ignore_permissions = True
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-9 Agreement insert ediliyor...")
		agreement_doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
		print(f"\n\n\n DEBUG-AGREEMENT-CREATE-10 Agreement başarıyla oluşturuldu: {agreement_doc.custom_restaurant_name}")
		print(f"\n\n\n ========== _CREATE_AGREEMENT BİTTİ ==========")
		
		frappe.logger().info(
			f"Agreement oluşturuldu: Customer={customer_name}, Supplier={supplier_name}, Name={agreement_doc.custom_restaurant_name}"
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
	print(f"\n\n\n DEBUG-AGREEMENT-AI-1 Customer: {doc.custom_restaurant_name}")
	
	try:
		# Agreement oluşturma WordPress sync'ten bağımsız çalışmalı
		# skip_wordpress_sync sadece WordPress'e geri göndermeyi atlar
		
		# Yeni vendor değerleri (1-6)
		new_vendors = {
			1: getattr(doc, "custom_brand_vendor_1", "") or "",
			2: getattr(doc, "custom_brand_vendor_2", "") or "",
			3: getattr(doc, "custom_brand_vendor_3", "") or "",
			4: getattr(doc, "custom_brand_vendor_4", "") or "",
			5: getattr(doc, "custom_brand_vendor_5", "") or "",
			6: getattr(doc, "custom_brand_vendor_6", "") or "",
		}
		
		print(f"\n\n\n DEBUG-AGREEMENT-AI-3 Yeni vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{new_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{new_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{new_vendors[3]}'")
		print(f"  custom_brand_vendor_4: '{new_vendors[4]}'")
		print(f"  custom_brand_vendor_5: '{new_vendors[5]}'")
		print(f"  custom_brand_vendor_6: '{new_vendors[6]}'")
		
		# Boş olmayan vendor'lar için agreement oluştur (1-6)
		for idx in [1, 2, 3, 4, 5, 6]:
			supplier = new_vendors[idx]
			if supplier:
				print(f"\n\n\n DEBUG-AGREEMENT-AI-4 Vendor {idx} bulundu: {supplier}")
				if frappe.db.exists("Supplier", supplier):
					print(f"\n\n\n DEBUG-AGREEMENT-AI-5 Supplier mevcut, agreement oluşturuluyor (Vendor Index={idx})")
					_create_agreement(doc.custom_restaurant_name, supplier, vendor_index=idx)
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


def create_agreements_for_customer_on_update(doc, method=None):
	"""
	Customer on_update hook'unda çalışır.
	WordPress webhook'undan geldiğinde before_save'de has_value_changed() çalışmayabilir,
	bu yüzden on_update'te de kontrol ediyoruz.
	"""
	print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER ON UPDATE BAŞLADI ==========")
	print(f"\n\n\n DEBUG-AGREEMENT-OU-1 Customer: {doc.custom_restaurant_name}")
	
	try:
		# Agreement oluşturma WordPress sync'ten bağımsız çalışmalı
		
		# Yeni değerler (1-6)
		new_vendors = {
			1: getattr(doc, "custom_brand_vendor_1", "") or "",
			2: getattr(doc, "custom_brand_vendor_2", "") or "",
			3: getattr(doc, "custom_brand_vendor_3", "") or "",
			4: getattr(doc, "custom_brand_vendor_4", "") or "",
			5: getattr(doc, "custom_brand_vendor_5", "") or "",
			6: getattr(doc, "custom_brand_vendor_6", "") or "",
		}
		
		print(f"\n\n\n DEBUG-AGREEMENT-OU-2 Yeni vendor değerleri:")
		print(f"  custom_brand_vendor_1: '{new_vendors[1]}'")
		print(f"  custom_brand_vendor_2: '{new_vendors[2]}'")
		print(f"  custom_brand_vendor_3: '{new_vendors[3]}'")
		print(f"  custom_brand_vendor_4: '{new_vendors[4]}'")
		print(f"  custom_brand_vendor_5: '{new_vendors[5]}'")
		print(f"  custom_brand_vendor_6: '{new_vendors[6]}'")
		
		# Eğer vendor değeri varsa ve agreement yoksa oluştur (1-6)
		for idx in [1, 2, 3, 4, 5, 6]:
			supplier = new_vendors[idx]
			
			if supplier and frappe.db.exists("Supplier", supplier):
				# Bu customer-supplier için zaten agreement var mı kontrol et
				existing_agreement = frappe.db.exists(
					"Agreement",
					{
						"customer": doc.custom_restaurant_name,
						"supplier": supplier,
						"docstatus": ["!=", 2]  # Cancel edilmemiş
					}
				)
				
				print(f"\n\n\n DEBUG-AGREEMENT-OU-3 Vendor {idx} ({supplier}) kontrolü:")
				print(f"  Mevcut agreement: {existing_agreement}")
				
				# Agreement yoksa oluştur
				if not existing_agreement:
					print(f"\n\n\n DEBUG-AGREEMENT-OU-4 Agreement oluşturuluyor: Customer={doc.custom_restaurant_name}, Supplier={supplier}, Vendor Index={idx}")
					_create_agreement(doc.custom_restaurant_name, supplier, vendor_index=idx)
				else:
					print(f"\n\n\n DEBUG-AGREEMENT-OU-5 Agreement zaten mevcut, atlanıyor")
		
		print("\n\n\n ========== CREATE AGREEMENTS FOR CUSTOMER ON UPDATE BİTTİ ==========")
		
	except Exception as e:
		print(f"\n\n\n DEBUG-AGREEMENT-OU-ERROR Exception: {str(e)}")
		print(f"\n\n\n DEBUG-AGREEMENT-OU-ERROR Traceback: {frappe.get_traceback()}")
		frappe.log_error(
			title="Customer Agreement Creation On Update Error",
			message=frappe.get_traceback()
		)

