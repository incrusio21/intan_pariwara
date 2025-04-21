# Copyright (c) 2025, DAS and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from erpnext.accounts.utils import get_fiscal_year

class StockEntry:
    def __init__(self, doc, method):
        self.doc = doc
        self.method = method

        if self.method == "on_submit":
            self.update_plafon_promosi()
            self.update_packing_qty()
        elif self.method == "on_cancel":
            self.update_plafon_promosi()
            self.update_packing_qty()

    def update_plafon_promosi(self):
        if self.doc.promotion_from == "Pusat" or self.doc.stock_entry_type not in ["Issue of Promotional Goods", "Receipt of Promotional Goods"]:
            return
        
        current_fiscal_year = get_fiscal_year(self.doc.posting_date, as_dict=True)
        
        promosi = frappe.get_doc("Plafon Promosi", {"fiscal_year": current_fiscal_year.name, "cabang": self.doc.promosi_branch}, for_update=1)
        promosi.set_remaining_plafon()

    def update_packing_qty(self):
        packing_list = {}

        for d in self.doc.get("items"):
            if d.packing_list:
                packing_list.setdefault(d.packing_list, []).append(d.packing_list_item)

        for pr, pr_item_rows in packing_list.items():
            if pr and pr_item_rows:
                pr_obj = frappe.get_doc("Packing List", pr)

                # if pr_obj.status in ["Stopped", "Cancelled"]:
                #     frappe.throw(
                #         _("{0} {1} is cancelled or stopped").format(_("Packing List"), pr),
                #         frappe.InvalidStatusError,
                #     )

                pr_obj.update_completed_qty(pr_item_rows)

def validasi_siplah_titipan(self, method):
    if self.stock_entry_type not in ["Siplah Titipan"]:
        return
    
    mr_list = set()
    for d in self.items:
        mr_list.add(d.material_request)

    for mr in mr_list:
        po = frappe.get_value("Material Request", mr, "pre_order")
        if po != self.pre_order:
            frappe.throw("Usage of item from Material Reqest {} is restricted due to Pre Order {}".format(mr, po))

@frappe.whitelist()
def scan_qr_barcode(search_value: str, material_transfer: str, purpose : None | str =None) -> BarcodeScanResult:
    qr_bundle = frappe.db.get_value(
        "Qr Code Packing Bundle",
        {"data_qr": search_value, "status": "Transit", "packing_purpose": purpose},
        ["name", "packing_list", "packing_purpose", "packing_docname"],
        as_dict=True,
    )
    if qr_bundle:
        qr_item = frappe.qb.DocType("Qr Code Bundle Item")
        ste_item = frappe.qb.DocType("Stock Entry Detail")
        item_qr_list = (
            frappe.qb.from_(qr_item)
            .inner_join(ste_item)
            .on(qr_item.document_detail == ste_item.material_request_item)
            .select(
                qr_item.parent.as_("qr_code_no"),
                qr_item.item_code,
                qr_item.qty,
                ste_item.name.as_("document_detail"),
                ste_item.parent.as_("document_name"),
                qr_item.stock_uom.as_("uom"),
            )
            .where(
                (qr_item.parent == qr_bundle.name) &
                (ste_item.parent == material_transfer)
            )
        ).run(as_dict=True)
            
        return item_qr_list

    return {}

@frappe.whitelist()
def make_stock_in_entry(source_name, target_doc=None):

    def set_missing_values(source, target):
        target.stock_entry_type = "Material Transfer"
        target.set_missing_values()

        target.from_warehouse = source.to_warehouse
        target.to_warehouse = source.custom_end_target
        if not frappe.db.get_single_value("Stock Settings", "use_serial_batch_fields"):
            target.make_serial_and_batch_bundle_for_transfer()

    def update_item(source_doc, target_doc, source_parent):
        target_doc.t_warehouse = ""

        if source_doc.material_request_item and source_doc.material_request:
            add_to_transit = frappe.db.get_value("Stock Entry", source_name, "add_to_transit")
            if add_to_transit:
                warehouse = frappe.get_value(
                    "Material Request Item", source_doc.material_request_item, "warehouse"
                )
                target_doc.t_warehouse = warehouse

        target_doc.s_warehouse = source_doc.t_warehouse
        target_doc.qty = source_doc.qty - source_doc.transferred_qty

    doclist = get_mapped_doc(
        "Stock Entry",
        source_name,
        {
            "Stock Entry": {
                "doctype": "Stock Entry",
                "field_map": {"name": "outgoing_stock_entry"},
                "validation": {"docstatus": ["=", 1]},
            },
            "Stock Entry Detail": {
            	"doctype": "Stock Entry Detail",
            	"field_map": {
            		"name": "ste_detail",
            		"parent": "against_stock_entry",
            		"serial_no": "serial_no",
            		"batch_no": "batch_no",
            	},
            	"postprocess": update_item,
            	"condition": lambda doc: not doc.qr_code_no,
            },
        },
        target_doc,
        set_missing_values,
    )

    return doclist

@frappe.whitelist()
def detail_item_request(item, from_warehouse=None, to_warehouse=None):
    ress = {}
    fields = []
    if not from_warehouse:
        fields.append("from_warehouse as s_warehouse")

    if not to_warehouse:
        fields.append("warehouse as t_warehouse")

    if fields:
        ress.update(
            frappe.get_value("Material Request Item", {"name": item}, fields, as_dict=1)
        )

    return ress