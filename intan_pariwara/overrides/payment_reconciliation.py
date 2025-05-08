import frappe

from erpnext.accounts.utils import _delete_gl_entries, _delete_pl_entries
from erpnext.accounts.doctype.payment_reconciliation.payment_reconciliation import PaymentReconciliation

class PaymentReconciliation(PaymentReconciliation):
	def reconcile_allocations(self, skip_ref_details_update_for_pe=False):
		super().reconcile_allocations(skip_ref_details_update_for_pe)
		for row in self.get("allocation"):
			repair_gle_ple(row.reference_type, row.reference_name)

# custom to re-generate GLE PLE from PaymentEntry / JournalEntry

@frappe.whitelist()
def repair_advances(doc,method):
	if doc.doctype in ["Sales Invoice"]:
		for row in doc.advances:
			repair_gle_ple(row.reference_type, row.reference_name)

def repair_gle_ple(doctype,docname):
	_delete_gl_entries(doctype, docname)
	_delete_pl_entries(doctype, docname)
	frappe.get_doc(doctype, docname).make_gl_entries()
