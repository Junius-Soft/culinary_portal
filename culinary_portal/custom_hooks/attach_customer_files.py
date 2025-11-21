import frappe
from frappe import _


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
		# WordPress sync'ten gelen update'leri atla
		if getattr(doc.flags, "skip_wordpress_sync", False):
			print("\n\n\n DEBUG-FILE-2 WordPress sync flag var, hook atlanıyor")
			return
		
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
			file_url = getattr(doc, field_name, "") or ""
			
			if not file_url:
				print(f"\n\n\n DEBUG-FILE-4 {field_name} boş, atlanıyor")
				continue
			
			print(f"\n\n\n DEBUG-FILE-5 {field_name} bulundu: {file_url}")
			
			# Bu URL zaten attach edilmiş mi kontrol et
			existing_file = frappe.db.exists(
				"File",
				{
					"file_url": file_url,
					"attached_to_doctype": "Customer",
					"attached_to_name": doc.name
				}
			)
			
			if existing_file:
				print(f"\n\n\n DEBUG-FILE-6 {field_name} zaten attach edilmiş: {existing_file}")
				continue
			
			# Dosyayı attach et
			try:
				file_name = f"{document_title}.pdf"
				
				# File doc oluştur
				file_doc = frappe.new_doc("File")
				file_doc.file_name = file_name
				file_doc.file_url = file_url
				file_doc.attached_to_doctype = "Customer"
				file_doc.attached_to_name = doc.name
				file_doc.is_private = 0
				file_doc.flags.ignore_permissions = True
				file_doc.flags.ignore_validate = True
				file_doc.flags.ignore_mandatory = True
				file_doc.insert()
				
				print(f"\n\n\n DEBUG-FILE-7 {field_name} başarıyla attach edildi: {file_doc.name}")
				
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

