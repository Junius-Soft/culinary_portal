import re
import frappe
from frappe import _
from frappe.utils.file_manager import save_file


TARGET_EMAIL_ACCOUNT = "noreply@ccculinary.de"


def extract_user_id_from_subject(subject):
	"""
	Mail başlığından user_id'yi çıkarır.
	Format: {{user_id}}- Title
	Örnek: "123- Document Title" -> 123
	"""
	if not subject:
		return None
	
	# Regex ile başlıktan user_id'yi çıkar
	# Format: {{user_id}}- veya user_id- şeklinde olabilir
	match = re.match(r'^(\d+)\s*-\s*', subject.strip())
	if match:
		return match.group(1)
	
	# Alternatif format: {{user_id}}- Title
	match = re.match(r'^\{\{(\d+)\}\}\s*-\s*', subject.strip())
	if match:
		return match.group(1)
	
	return None


def get_communication_attachments(communication_name):
	"""
	Communication'a bağlı File'ları (attachments) döndürür.
	"""
	attachments = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Communication",
			"attached_to_name": communication_name,
		},
		fields=["name", "file_name", "file_url", "is_private"],
	)
	return attachments


def attach_file_to_customer(file_doc, customer_name, email_subject):
	"""
	File'ı Customer'a attach eder.
	Eğer aynı dosya zaten customer'a attach edilmişse, tekrar eklemez.
	"""
	# Aynı file_url ve customer için zaten attach edilmiş mi kontrol et
	existing_file = frappe.db.exists(
		"File",
		{
			"attached_to_doctype": "Customer",
			"attached_to_name": customer_name,
			"file_url": file_doc.file_url,
		}
	)
	
	if existing_file:
		print(f"\n\n\n DEBUG-EMAIL-ATTACH: Dosya zaten customer'a attach edilmiş: {existing_file}")
		return existing_file
	
	# Yeni File kaydı oluştur
	new_file = frappe.new_doc("File")
	new_file.file_name = file_doc.file_name
	new_file.file_url = file_doc.file_url
	new_file.attached_to_doctype = "Customer"
	new_file.attached_to_name = customer_name
	new_file.is_private = file_doc.is_private or 0
	new_file.flags.ignore_permissions = True
	new_file.flags.ignore_validate = True
	new_file.flags.ignore_mandatory = True
	new_file.insert(ignore_permissions=True)
	frappe.db.commit()
	
	print(f"\n\n\n DEBUG-EMAIL-ATTACH: Dosya customer'a attach edildi: {new_file.name}")
	return new_file.name


def is_already_processed(communication_name):
	"""
	Bu Communication için attachments zaten işlenmiş mi kontrol eder.
	"""
	# Communication'ın custom field'ında işaret var mı kontrol et
	# Veya File'ların customer'a attach edilip edilmediğini kontrol et
	# Şimdilik basit bir cache kontrolü yapalım
	cache_key = f"email_attachments_processed_{communication_name}"
	return frappe.cache().get_value(cache_key)


def mark_as_processed(communication_name):
	"""
	Bu Communication'ı işlendi olarak işaretler.
	"""
	cache_key = f"email_attachments_processed_{communication_name}"
	frappe.cache().set_value(cache_key, True, expires_in_sec=86400)  # 24 saat


def process_email_attachments(doc, method=None):
	"""
	Communication doctype'ı için hook fonksiyonu.
	noreply@ccculinary.de email hesabına gelen maillerin attachments'larını
	mail başlığındaki user_id'ye göre customer'a attach eder.
	
	Mail başlığı formatı: {{user_id}}- Title veya user_id- Title
	
	Hem after_insert hem de on_update hook'larından çağrılabilir.
	Duplicate işlemleri önlemek için cache kontrolü yapılır.
	"""
	print("\n\n\n ========== PROCESS EMAIL ATTACHMENTS BAŞLADI ==========")
	print(f"\n\n\n DEBUG-EMAIL-1 Communication: {doc.name}")
	
	# Zaten işlenmiş mi kontrol et
	if is_already_processed(doc.name):
		print(f"\n\n\n DEBUG-EMAIL-SKIP: Communication zaten işlenmiş: {doc.name}")
		return
	
	try:
		# Sadece gelen mailleri işle (sent_or_received = "Received")
		if hasattr(doc, 'sent_or_received') and doc.sent_or_received != "Received":
			print(f"\n\n\n DEBUG-EMAIL-2 Communication sent_or_received uygun değil: {getattr(doc, 'sent_or_received', 'N/A')}")
			return
		
		# Email Account kontrolü - farklı field isimlerini dene
		email_account = None
		if hasattr(doc, 'email_account') and doc.email_account:
			email_account = doc.email_account
		elif hasattr(doc, 'email_account_name') and doc.email_account_name:
			email_account = doc.email_account_name
		
		if not email_account:
			# Email account field'ı yoksa, recipient'ten kontrol et
			recipient = getattr(doc, 'recipients', '') or getattr(doc, 'recipient', '')
			if TARGET_EMAIL_ACCOUNT in str(recipient):
				print(f"\n\n\n DEBUG-EMAIL-3 Email account field yok ama recipient uygun: {recipient}")
			else:
				print(f"\n\n\n DEBUG-EMAIL-3 Email account bulunamadı ve recipient uygun değil: {recipient}")
				return
		else:
			# Email Account'ın email_id'sini kontrol et
			try:
				email_account_doc = frappe.get_doc("Email Account", email_account)
				email_id = email_account_doc.email_id
				
				if email_id != TARGET_EMAIL_ACCOUNT:
					print(f"\n\n\n DEBUG-EMAIL-4 Email account uygun değil: {email_id} (beklenen: {TARGET_EMAIL_ACCOUNT})")
					return
				
				print(f"\n\n\n DEBUG-EMAIL-5 Email account uygun: {email_id}")
			except Exception as e:
				print(f"\n\n\n DEBUG-EMAIL-ERROR Email account okuma hatası: {str(e)}")
				# Email account okunamazsa, recipient'ten kontrol et
				recipient = getattr(doc, 'recipients', '') or getattr(doc, 'recipient', '')
				if TARGET_EMAIL_ACCOUNT not in str(recipient):
					print(f"\n\n\n DEBUG-EMAIL-3 Recipient uygun değil: {recipient}")
					return
				print(f"\n\n\n DEBUG-EMAIL-5 Recipient uygun: {recipient}")
		
		# Mail başlığından user_id'yi çıkar
		subject = doc.subject or ""
		user_id = extract_user_id_from_subject(subject)
		
		if not user_id:
			print(f"\n\n\n DEBUG-EMAIL-6 Mail başlığından user_id çıkarılamadı. Subject: {subject}")
			return
		
		print(f"\n\n\n DEBUG-EMAIL-7 User ID bulundu: {user_id}")
		
		# Customer'ı custom_portal_user_id ile bul
		customer = frappe.db.get_value(
			"Customer",
			{"custom_portal_user_id": user_id},
			["name", "customer_name"],
			as_dict=True
		)
		
		if not customer:
			print(f"\n\n\n DEBUG-EMAIL-8 Customer bulunamadı: custom_portal_user_id={user_id}")
			frappe.log_error(
				title="Email Attachment: Customer Not Found",
				message=f"User ID: {user_id}\nSubject: {subject}\nCommunication: {doc.name}"
			)
			return
		
		print(f"\n\n\n DEBUG-EMAIL-9 Customer bulundu: {customer.name} ({customer.customer_name})")
		
		# Communication'a bağlı attachments'ları al
		attachments = get_communication_attachments(doc.name)
		
		if not attachments:
			print(f"\n\n\n DEBUG-EMAIL-10 Communication'da attachment bulunamadı")
			return
		
		print(f"\n\n\n DEBUG-EMAIL-11 {len(attachments)} adet attachment bulundu")
		
		# Her attachment'ı customer'a attach et
		attached_files = []
		for attachment in attachments:
			try:
				file_doc = frappe.get_doc("File", attachment.name)
				file_name = attach_file_to_customer(file_doc, customer.name, subject)
				attached_files.append(file_name)
			except Exception as e:
				print(f"\n\n\n DEBUG-EMAIL-ERROR Attachment işleme hatası: {str(e)}")
				frappe.log_error(
					title="Email Attachment: File Attach Error",
					message=f"File: {attachment.name}\nCustomer: {customer.name}\nError: {str(e)}\n{frappe.get_traceback()}"
				)
		
		print(f"\n\n\n DEBUG-EMAIL-12 {len(attached_files)} adet dosya customer'a attach edildi")
		
		# İşlendi olarak işaretle (sadece başarılı olursa)
		if attached_files:
			mark_as_processed(doc.name)
		
		print("\n\n\n ========== PROCESS EMAIL ATTACHMENTS BİTTİ ==========")
		
	except Exception as e:
		print(f"\n\n\n DEBUG-EMAIL-ERROR Exception: {str(e)}")
		print(f"\n\n\n DEBUG-EMAIL-ERROR Traceback: {frappe.get_traceback()}")
		frappe.log_error(
			title="Email Attachment: Process Error",
			message=f"Communication: {doc.name}\nError: {str(e)}\n{frappe.get_traceback()}"
		)

