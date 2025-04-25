import frappe

def test():
	pr = frappe.get_doc({
    "name": "Payment Reconciliation",
    "minimum_invoice_amount": 0,
    "minimum_payment_amount": 0,
    "maximum_invoice_amount": 0,
    "maximum_payment_amount": 0,
    "invoice_limit": 50,
    "payment_limit": 50,
    "doctype": "Payment Reconciliation",
    "allocation": [
        {
            "docstatus": 0,
            "idx": 1,
            "reference_type": "Payment Entry",
            "reference_name": "ACC-PAY-2025-00076",
            "invoice_type": "Sales Invoice",
            "invoice_number": "ACC-SINV-2025-00048",
            "allocated_amount": 6000,
            "unreconciled_amount": 742750,
            "amount": 742750,
            "difference_amount": 0,
            "gain_loss_posting_date": "2025-04-15",
            "exchange_rate": 1,
            "currency": "IDR",
            "parent": "Payment Reconciliation",
            "parentfield": "allocation",
            "parenttype": "Payment Reconciliation",
            "doctype": "Payment Reconciliation Allocation",
            "__islocal": 1,
            "name": "new-payment-reconciliation-allocation-kttbxwbtmf"
        }
    ],
    "payments": [
        {
            "docstatus": 0,
            "idx": 1,
            "reference_type": "Payment Entry",
            "reference_name": "ACC-PAY-2025-00075",
            "posting_date": "2025-04-12",
            "amount": 1000000,
            "difference_amount": 0,
            "remarks": "Amount IDR 1000000.0 received from R18090001\nTransaction reference no kode ref dated 2025-04-12",
            "currency": "IDR",
            "exchange_rate": 1,
            "parent": "Payment Reconciliation",
            "parentfield": "payments",
            "parenttype": "Payment Reconciliation",
            "doctype": "Payment Reconciliation Payment",
            "__islocal": 1,
            "name": "new-payment-reconciliation-twoxatzhpl"
        },
        {
            "docstatus": 0,
            "idx": 2,
            "reference_type": "Payment Entry",
            "reference_name": "ACC-PAY-2025-00076",
            "posting_date": "2025-04-15",
            "amount": 742750,
            "difference_amount": 0,
            "remarks": "Amount IDR 1000000.0 received from R18090001\nTransaction reference no ref no dated 2025-04-15\nAmount IDR 251250.0 against Sales Invoice ACC-SINV-2025-00051",
            "currency": "IDR",
            "exchange_rate": 1,
            "parent": "Payment Reconciliation",
            "parentfield": "payments",
            "parenttype": "Payment Reconciliation",
            "doctype": "Payment Reconciliation Payment",
            "__islocal": 1,
            "name": "new-payment-reconciliation-nxeolmtdok"
        },
        {
            "docstatus": 0,
            "idx": 3,
            "reference_type": "Sales Invoice",
            "reference_name": "ACC-SINV-2025-00057",
            "posting_date": "2025-04-15",
            "amount": 232700,
            "difference_amount": 0,
            "remarks": "No Remarks",
            "currency": "IDR",
            "exchange_rate": 0,
            "parent": "Payment Reconciliation",
            "parentfield": "payments",
            "parenttype": "Payment Reconciliation",
            "doctype": "Payment Reconciliation Payment",
            "__islocal": 1,
            "name": "new-payment-reconciliation-ngihqbolhn"
        }
    ],
    "invoices": [
        {
            "docstatus": 0,
            "idx": 1,
            "invoice_type": "Sales Invoice",
            "invoice_number": "ACC-SINV-2025-00048",
            "invoice_date": "2025-03-27",
            "amount": 790500,
            "outstanding_amount": 6000,
            "currency": "IDR",
            "exchange_rate": 0,
            "parent": "Payment Reconciliation",
            "parentfield": "invoices",
            "parenttype": "Payment Reconciliation",
            "doctype": "Payment Reconciliation Invoice",
            "__islocal": 1,
            "name": "new-payment-reconciliation-invoice-xwxhocczxp"
        }
    ],
    "company": "Intan Pariwara Vitarana",
    "party_type": "Customer",
    "party": "R18090001",
    "receivable_payable_account": "1131.001 - Piutang Dagang - Pihak Ketiga - IPV",
    "default_advance_account": "2121.001 - Uang Muka Penjualan Reguler - IPV",
    "docstatus": 0,
    "idx": 0
})

	pr.reconcile()