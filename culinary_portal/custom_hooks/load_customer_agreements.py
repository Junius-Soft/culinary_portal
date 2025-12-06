import frappe
from frappe import _


def load_customer_agreements(doc, method=None):
	"""
	Customer form açıldığında (on_load), custom_customer_agreements table field'ına
	(Customer Aggrements child doctype) Agreement verilerini yükler.
	
	Bu tablo read-only olarak gösterilir, sadece görüntüleme amaçlıdır.
	name1 field'ı Agreement'a link olarak gösterilir.
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
			doc.append("custom_customer_agreements", {
				"name1": agreement.name,
				"supplier": agreement.supplier,
				"valid_from": agreement.valid_from,
				"valid_to": agreement.valid_to,
				"status": agreement.status
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

