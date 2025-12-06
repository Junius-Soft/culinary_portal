import frappe
from frappe import _


def load_customer_agreements(doc, method=None):
	"""
	Customer form açıldığında (on_load), custom_customer_agreements table field'ına
	(Customer Aggrements child doctype) Agreement verilerini yükler.
	
	Her Agreement için:
	- name1: Agreement link
	- supplier, valid_from, valid_to, status: Agreement bilgileri
	- services: Agreement Services'lerden gelen service'ler (virgülle ayrılmış)
	
	Bu tablo read-only olarak gösterilir, sadece görüntüleme amaçlıdır.
	"""
	if not doc.name or doc.get("__islocal"):
		return
	
	try:
		# Customer'a ait Agreement'ları çek
		agreements = frappe.get_all(
			"Agreement",
			filters={
				"customer": doc.name
			},
			fields=[
				"name",
				"supplier",
				"valid_from",
				"valid_to",
				"status",
				"docstatus"
			],
			order_by="creation desc"
		)
		
		# Mevcut child table'ı temizle (sadece memory'de, DB'ye yazılmaz)
		doc.set("custom_customer_agreements", [])
		
		# Agreement'ları child table'a ekle
		for agreement in agreements:
			# Agreement Services'leri çek
			agreement_services = frappe.get_all(
				"Agreement Services",
				filters={
					"parent": agreement.name,
					"parenttype": "Agreement"
				},
				fields=["service"],
				order_by="idx"
			)
			
			# Services'leri virgülle ayrılmış string olarak birleştir
			services_list = [s.service for s in agreement_services if s.service]
			services_text = ", ".join(services_list) if services_list else ""
			
			doc.append("custom_customer_agreements", {
				"name1": agreement.name,
				"supplier": agreement.supplier,
				"valid_from": agreement.valid_from,
				"valid_to": agreement.valid_to,
				"status": agreement.status,
				"services": services_text
			})
		
		# Bu field'lar DB'ye kaydedilmesin (sadece görüntüleme için)
		if hasattr(doc, "custom_customer_agreements"):
			for row in doc.custom_customer_agreements:
				row.db_set = lambda *args, **kwargs: None  # DB'ye yazma
		
	except Exception as e:
		frappe.log_error(
			title="Load Customer Agreements Error",
			message=f"Customer: {doc.name}\nError: {str(e)}\n{frappe.get_traceback()}"
		)

