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
				limit=1,
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
				# Eski dosyayi sil (varsa)
				if existing_files:
					for old_file in existing_files:
						if old_file.name:
							frappe.delete_doc("File", old_file.name, ignore_permissions=True)
							print(f"\n\n\n DEBUG-FILE-6 {field_name} için eski dosya silindi: {old_file.name}")

				file_doc = save_file(
					fname=file_name,
					content=file_content,
					dt="Customer",
					dn=doc.name,
					df=field_name,
					is_private=0,
				)

				print(f"\n\n\n DEBUG-FILE-7 {field_name} başariyla indirildi ve attach edildi: {file_doc.name}")

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

