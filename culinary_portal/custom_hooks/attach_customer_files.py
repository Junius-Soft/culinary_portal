import os
from urllib.parse import urlparse

import requests
import frappe
from frappe import _
from frappe.utils.file_manager import save_file


DOWNLOAD_TIMEOUT = 30
LOCAL_FILE_PREFIXES = ("/files/", "/private/files/")


def is_local_file_url(file_url):
	"""Dosyanın ERP içinde saklanıp saklanmadığını kontrol eder."""
	if not file_url:
		return False
	file_path = urlparse(file_url).path or ""
	return file_path.startswith(LOCAL_FILE_PREFIXES)


def build_file_name(document_title, file_url):
	"""Uzak dosya uzantısını koruyarak hedef dosya adını üretir."""
	path = urlparse(file_url or "").path
	extension = os.path.splitext(path)[1]
	if not extension:
		extension = ".pdf"
	return f"{document_title}{extension}"


def download_remote_file(file_url):
	"""Uzak dosyayı indirip binary içeriğini döner."""
	response = requests.get(file_url, timeout=DOWNLOAD_TIMEOUT)
	response.raise_for_status()
	return response.content


def attach_customer_files_on_update(doc, method=None):
	"""
	Customer update olduğunda dosya alanlarındaki URL'leri alıp Customer'a attach eder.
	
	Dosya alanları:
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
		# Flag kontrolü - tekrar çalışmasını önle
		if getattr(doc.flags, "culinary_file_attach_ran", False):
			print("\n\n\n DEBUG-FILE-3 Flag var, hook atlanıyor")
			return
		doc.flags.culinary_file_attach_ran = True
		
		# Dosya alanları ve document title mapping'i
		file_fields = {
			"custom_business_registration_file": "Business Registration File",
			"custom_id_file": "ID File",
			"custom_hr_extract_file": "HR Extract File",
			"custom_shareholder_list_file": "Shareholder List File",
			"custom_register_extract_file": "Register Extract File",
		}
		
		# Her dosya alanı için kontrol et
		for field_name, document_title in file_fields.items():
			file_url = (getattr(doc, field_name, "") or "").strip()
			
			if not file_url:
				print(f"\n\n\n DEBUG-FILE-4 {field_name} boş, atlanıyor")
				continue
			
			print(f"\n\n\n DEBUG-FILE-5 {field_name} bulundu: {file_url}")
			
			file_name = build_file_name(document_title, file_url)
			existing_file = frappe.get_all(
				"File",
				{
					"attached_to_doctype": "Customer",
					"attached_to_name": doc.name,
					"attached_to_field": field_name,
				},
				["name", "file_url", "description"],
				limit=1,
			)
			file_to_remove = None
			
			if existing_file:
				file_to_remove = existing_file[0].name
				
				if is_local_file_url(existing_file[0].file_url) and existing_file[0].description == file_url:
					print(f"\n\n\n DEBUG-FILE-6 {field_name} için yerel dosya zaten var: {existing_file[0].name}")
					continue
			
			# Dosyayı indir ve attach et
			try:
				file_content = download_remote_file(file_url)
			except requests.RequestException as err:
				print(f"\n\n\n DEBUG-FILE-ERROR {field_name} download hatası: {str(err)}")
				frappe.log_error(
					title="Customer File Download Error",
					message=f"Field: {field_name}\nURL: {file_url}\nError: {str(err)}\n{frappe.get_traceback()}"
				)
				continue
			
			try:
				file_doc = save_file(
					fname=file_name,
					content=file_content,
					dt="Customer",
					dn=doc.name,
					df=field_name,
					is_private=0,
				)
				
				# Kaynağı takip edebilmek için orijinal URL'i description'a yaz
				frappe.db.set_value(
					"File",
					file_doc.name,
					"description",
					file_url,
					update_modified=False,
				)
				
				print(f"\n\n\n DEBUG-FILE-7 {field_name} başarıyla indirildi ve attach edildi: {file_doc.name}")
				
				if file_to_remove and file_to_remove != file_doc.name:
					frappe.delete_doc("File", file_to_remove, ignore_permissions=True)
				
			except Exception as e:
				print(f"\n\n\n DEBUG-FILE-ERROR {field_name} attach hatası: {str(e)}")
				frappe.log_error(
					title="Customer File Attach Error",
					message=f"Field: {field_name}\nURL: {file_url}\nError: {str(e)}\n{frappe.get_traceback()}"
				)
		
		frappe.db.commit()
		print("\n\n\n ========== ATTACH CUSTOMER FILES BİTTİ ==========")
		
	except Exception as e:
		print(f"\n\n\n DEBUG-FILE-ERROR Exception: {str(e)}")
		print(f"\n\n\n DEBUG-FILE-ERROR Traceback: {frappe.get_traceback()}")
		frappe.log_error(
			title="Customer File Attach Exception",
			message=frappe.get_traceback()
		)

