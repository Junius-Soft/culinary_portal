import hashlib
import os
from urllib.parse import urlparse

import requests
import frappe
from frappe import _
from frappe.utils.file_manager import save_file


DOWNLOAD_TIMEOUT = 30
LOCAL_FILE_PREFIXES = ("/files/", "/private/files/")


def is_local_file_url(file_url):
	"""Dosyanin ERP içinde saklanip saklanmadiğini kontrol eder."""
	if not file_url:
		return False
	file_path = urlparse(file_url).path or ""
	return file_path.startswith(LOCAL_FILE_PREFIXES)


def build_file_name(document_title, file_url):
	"""Uzak dosya uzantisini koruyarak hedef dosya adini üretir."""
	path = urlparse(file_url or "").path
	extension = os.path.splitext(path)[1]
	if not extension:
		extension = ".pdf"
	return f"{document_title}{extension}"


def download_remote_file(file_url):
	"""Uzak dosyayi indirip binary içeriğini döner."""
	response = requests.get(file_url, timeout=DOWNLOAD_TIMEOUT)
	response.raise_for_status()
	return response.content


def attach_customer_files_on_update(doc, method=None):
	"""
	Customer update olduğunda dosya alanlarindaki URL'leri alip Customer'a attach eder.

	Dosya alanlari:
	- custom_business_registration_file
	- custom_id_file
	- custom_hr_extract_file
	- custom_shareholder_list_file
	- custom_register_extract_file

	Her dosya için sadece bir kere attach eder (tekrar eklemez).
	Ayni dosya birden fazla alana girildiğinde her alana ayrı ayrı attach edilir.
	"""
	print("\n\n\n ========== ATTACH CUSTOMER FILES BAŞLADI ==========")
	print(f"\n\n\n DEBUG-FILE-1 Customer: {doc.name}")

	try:
		# Dosya alanlari ve document title mapping'i
		file_fields = {
			"custom_business_registration_file": "Business Registration File",
			"custom_id_file": "ID File",
			"custom_hr_extract_file": "HR Extract File",
			"custom_shareholder_list_file": "Shareholder List File",
			"custom_register_extract_file": "Register Extract File",
		}

		# Eski değerleri veritabanından al (değişiklik kontrolü için)
		old_doc = None
		if doc.name and frappe.db.exists("Customer", doc.name):
			old_doc = frappe.get_doc("Customer", doc.name)

		# Her dosya alani için kontrol et
		for field_name, document_title in file_fields.items():
			file_url = (getattr(doc, field_name, "") or "").strip()

			if not file_url:
				print(f"\n\n\n DEBUG-FILE-4 {field_name} boş, atlaniyor")
				continue

			print(f"\n\n\n DEBUG-FILE-5 {field_name} bulundu: {file_url}")

			# Sadece uzak URL'leri isle (http/https ile baslayanlar)
			if not file_url.startswith(("http://", "https://")):
				print(f"\n\n\n DEBUG-FILE-4 {field_name} yerel dosya, atlaniyor: {file_url}")
				continue

			# Bu field için mevcut dosyayı kontrol et
			# ÖNEMLİ: Aynı URL farklı field'lara eklenebilir, bu yüzden kontrol sadece bu field için yapılmalı
			existing_file_for_field = frappe.db.exists(
				"File",
				{
					"attached_to_doctype": "Customer",
					"attached_to_name": doc.name,
					"attached_to_field": field_name,  # Sadece bu field için kontrol
				}
			)

			# Değişiklik kontrolü: Eğer URL değişmediyse ve bu field için dosya zaten varsa işlem yapma
			if old_doc and existing_file_for_field:
				old_file_url = (getattr(old_doc, field_name, "") or "").strip()
				print(f"\n\n\n DEBUG-FILE-9 {field_name} old_file_url: '{old_file_url}', new_file_url: '{file_url}'")
				# Sadece bu field'ın eski URL'si ile karşılaştır
				if old_file_url == file_url:
					# URL aynı ve dosya zaten bu field'a attach edilmiş - atla
					print(f"\n\n\n DEBUG-FILE-8 {field_name} URL değişmedi ve dosya zaten bu field'a attach edilmiş, atlaniyor")
					continue
				else:
					# URL değişmiş - işleme devam et (eski dosya silinecek, yeni dosya eklenecek)
					print(f"\n\n\n DEBUG-FILE-11 {field_name} URL değişti, işleme devam ediliyor")
			elif existing_file_for_field:
				# old_doc yok ama dosya var - muhtemelen yeni kayıt veya ilk kez ekleniyor
				# Aynı URL başka bir field'a eklenmiş olsa bile bu field için ekleme yapılmalı
				print(f"\n\n\n DEBUG-FILE-12 {field_name} dosya var ama old_doc kontrolü yapılamadı, işleme devam ediliyor")
			else:
				# Bu field için dosya yok - işleme devam et
				print(f"\n\n\n DEBUG-FILE-13 {field_name} bu field için dosya yok, işleme devam ediliyor")

			file_name = build_file_name(document_title, file_url)

			# Ayni field için mevcut dosyayi bul
			existing_files = frappe.get_all(
				"File",
				{
					"attached_to_doctype": "Customer",
					"attached_to_name": doc.name,
					"attached_to_field": field_name,
				},
				["name", "file_url"],
			)

			# Dosyayi indir ve attach et
			try:
				file_content = download_remote_file(file_url)
			except requests.RequestException as err:
				print(f"\n\n\n DEBUG-FILE-ERROR {field_name} download hatasi: {str(err)}")
				frappe.log_error(
					title="Customer File Download Error",
					message=f"Field: {field_name}\nURL: {file_url}\nError: {str(err)}\n{frappe.get_traceback()}"
				)
				continue

			try:
				# Content hash'i hesapla (duplicate kontrolü için)
				content_hash = hashlib.md5(file_content).hexdigest()
				
				# Bu field için aynı content hash'e sahip dosya zaten var mı?
				existing_by_hash = frappe.get_all(
					"File",
					{
						"attached_to_doctype": "Customer",
						"attached_to_name": doc.name,
						"attached_to_field": field_name,
						"content_hash": content_hash,
					},
					["name"],
					limit=1,
				)
				
				if existing_by_hash:
					print(f"\n\n\n DEBUG-FILE-8 {field_name} için aynı içerik zaten bu field'a mevcut: {existing_by_hash[0].name}")
					# Aynı içerik zaten bu field'a var, eski dosyaları sil (eğer farklı dosyalarsa)
					if existing_files:
						for old_file in existing_files:
							if old_file.name and old_file.name != existing_by_hash[0].name:
								frappe.delete_doc("File", old_file.name, ignore_permissions=True)
								print(f"\n\n\n DEBUG-FILE-6 {field_name} için eski dosya silindi: {old_file.name}")
				else:
					# Eski dosyayi sil (varsa) - sadece bu field'a ait olanları
					if existing_files:
						for old_file in existing_files:
							if old_file.name:
								frappe.delete_doc("File", old_file.name, ignore_permissions=True)
								print(f"\n\n\n DEBUG-FILE-6 {field_name} için eski dosya silindi: {old_file.name}")

					# Dosyayı attach et - her field için ayrı File kaydı oluşturulacak
					# ÖNEMLİ: Aynı dosya farklı field'lara eklenebilir, her biri için ayrı File kaydı olmalı
					
					# Önce aynı content_hash'e sahip başka bir field'a bağlı dosya var mı kontrol et
					other_field_file = frappe.get_all(
						"File",
						filters=[
							["attached_to_doctype", "=", "Customer"],
							["attached_to_name", "=", doc.name],
							["content_hash", "=", content_hash],
							["attached_to_field", "!=", field_name],  # Bu field dışındaki field'lar
						],
						fields=["name", "file_name", "file_url", "folder", "file_size", "is_private"],
						limit=1,
					)
					
					if other_field_file:
						# Aynı dosya başka bir field'a bağlı - bu field için yeni bir File kaydı oluştur
						other_file_doc = frappe.get_doc("File", other_field_file[0].name)
						new_file = frappe.get_doc({
							"doctype": "File",
							"file_name": file_name,  # Bu field için özel isim
							"file_url": other_file_doc.file_url,
							"attached_to_doctype": "Customer",
							"attached_to_name": doc.name,
							"attached_to_field": field_name,  # Bu field'a bağla
							"folder": other_file_doc.folder,
							"file_size": other_file_doc.file_size,
							"content_hash": other_file_doc.content_hash,
							"is_private": other_file_doc.is_private,
						})
						new_file.flags.ignore_permissions = True
						try:
							new_file.insert(ignore_permissions=True)
							print(f"\n\n\n DEBUG-FILE-9 {field_name} için aynı dosyanın kopyası oluşturuldu: {new_file.name}")
						except frappe.DuplicateEntryError:
							# Duplicate entry - muhtemelen aynı anda başka bir işlem de eklemiş
							# Mevcut dosyayı kontrol et
							existing = frappe.get_all(
								"File",
								{
									"attached_to_doctype": "Customer",
									"attached_to_name": doc.name,
									"attached_to_field": field_name,
									"content_hash": content_hash,
								},
								["name"],
								limit=1,
							)
							if existing:
								print(f"\n\n\n DEBUG-FILE-10 {field_name} için dosya zaten mevcut (duplicate): {existing[0].name}")
							else:
								raise
					else:
						# Aynı dosya başka field'a bağlı değil - normal şekilde ekle
						try:
							file_doc = save_file(
								fname=file_name,
								content=file_content,
								dt="Customer",
								dn=doc.name,
								df=field_name,
								is_private=1,
							)
							# Dönen dosyanın doğru field'a bağlı olduğunu kontrol et
							if hasattr(file_doc, 'attached_to_field') and file_doc.attached_to_field != field_name:
								# Yanlış field'a bağlı - yeni bir File kaydı oluştur
								print(f"\n\n\n DEBUG-FILE-WARN {field_name} için dosya yanlış field'a bağlı, yeni kayıt oluşturuluyor")
								actual_file = frappe.get_doc("File", file_doc.name)
								new_file = frappe.get_doc({
									"doctype": "File",
									"file_name": file_name,
									"file_url": actual_file.file_url,
									"attached_to_doctype": "Customer",
									"attached_to_name": doc.name,
									"attached_to_field": field_name,
									"folder": actual_file.folder,
									"file_size": actual_file.file_size,
									"content_hash": actual_file.content_hash,
									"is_private": actual_file.is_private,
								})
								new_file.flags.ignore_permissions = True
								new_file.insert(ignore_permissions=True)
								file_doc = new_file
							print(f"\n\n\n DEBUG-FILE-7 {field_name} başariyla indirildi ve attach edildi: {file_doc.name}")
						except frappe.DuplicateEntryError:
							# Duplicate entry hatası - aynı content hash ile başka bir field'a attach edilmiş dosya var
							# Bu durumda, aynı dosyayı bu field için de oluştur
							other_file = frappe.get_all(
								"File",
								{"content_hash": content_hash},
								["name"],
								limit=1,
							)
							if other_file:
								other_file_doc = frappe.get_doc("File", other_file[0].name)
								# Aynı dosyanın bu field için yeni bir kopyasını oluştur
								new_file = frappe.get_doc({
									"doctype": "File",
									"file_name": file_name,
									"file_url": other_file_doc.file_url,
									"attached_to_doctype": "Customer",
									"attached_to_name": doc.name,
									"attached_to_field": field_name,
									"folder": other_file_doc.folder,
									"file_size": other_file_doc.file_size,
									"content_hash": other_file_doc.content_hash,
									"is_private": other_file_doc.is_private,
								})
								new_file.flags.ignore_permissions = True
								new_file.insert(ignore_permissions=True)
								print(f"\n\n\n DEBUG-FILE-9 {field_name} için aynı dosyanın kopyası oluşturuldu: {new_file.name}")

			except Exception as e:
				print(f"\n\n\n DEBUG-FILE-ERROR {field_name} attach hatasi: {str(e)}")
				frappe.log_error(
					title="Customer File Attach Error",
					message=f"Field: {field_name}\nURL: {file_url}\nError: {str(e)}\n{frappe.get_traceback()}"
				)

		frappe.db.commit()
		print("\n\n\n ========== ATTACH CUSTOMER FILES BITTI ==========")

	except Exception as e:
		print(f"\n\n\n DEBUG-FILE-ERROR Exception: {str(e)}")
		print(f"\n\n\n DEBUG-FILE-ERROR Traceback: {frappe.get_traceback()}")
		frappe.log_error(
			title="Customer File Attach Exception",
			message=frappe.get_traceback()
		)

