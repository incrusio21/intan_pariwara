# Copyright (c) 2025, DAS and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.delete_doc import raise_link_exists_exception
from frappe.model.docstatus import DocStatus
from frappe.model.dynamic_links import get_dynamic_link_map

def check_if_doc_is_linked(doc, method="Cancel"):
	"""
	Raises excption if the given doc(dt, dn) is linked in another record.
	"""
	from frappe.model.rename_doc import get_link_fields

	link_fields = get_link_fields(doc.doctype)
	ignored_doctypes = set()

	if method == "Cancel" and (doc_ignore_flags := doc.get("ignore_linked_doctypes")):
		ignored_doctypes.update(doc_ignore_flags)
	if method == "Delete":
		ignored_doctypes.update(frappe.get_hooks("ignore_links_on_delete"))

	for lf in link_fields:
		link_dt, link_field, issingle = lf["parent"], lf["fieldname"], lf["issingle"]
		if link_dt in ignored_doctypes or (link_field == "amended_from" and method == "Cancel"):
			continue

		try:
			meta = frappe.get_meta(link_dt)
		except frappe.DoesNotExistError:
			frappe.clear_last_message()
			# This mostly happens when app do not remove their customizations, we shouldn't
			# prevent link checks from failing in those cases
			continue

		if issingle:
			if frappe.db.get_single_value(link_dt, link_field) == doc.name:
				raise_link_exists_exception(doc, link_dt, link_dt)
			continue

		fields = ["name", "docstatus"]

		if meta.istable:
			fields.extend(["parent", "parenttype"])

		for item in frappe.db.get_values(link_dt, {link_field: doc.name}, fields, as_dict=True):
			# available only in child table cases
			item_parent = getattr(item, "parent", None)
			linked_parent_doctype = item.parenttype if item_parent else link_dt

			if linked_parent_doctype in ignored_doctypes:
				continue

			if method != "Delete" and (method != "Cancel" or DocStatus(item.docstatus).is_cancelled()):
				# don't raise exception if not
				# linked to a non-cancelled doc when deleting or to a submitted doc when cancelling
				continue
			elif link_dt == doc.doctype and (item_parent or item.name) == doc.name:
				# don't raise exception if not
				# linked to same item or doc having same name as the item
				continue
			else:
				reference_docname = item_parent or item.name
				raise_link_exists_exception(doc, linked_parent_doctype, reference_docname)


def check_if_doc_is_dynamically_linked(doc, method="Cancel"):
	"""Raise `frappe.LinkExistsError` if the document is dynamically linked"""
	for df in get_dynamic_link_map().get(doc.doctype, []):
		ignore_linked_doctypes = (doc.get("ignore_linked_doctypes") or []) + ["Workflow Action"]

		if df.parent in frappe.get_hooks("ignore_links_on_delete") or (
			df.parent in ignore_linked_doctypes and method == "Cancel"
		):
			# don't check for communication and todo!
			continue

		meta = frappe.get_meta(df.parent)
		if meta.issingle:
			# dynamic link in single doc
			refdoc = frappe.db.get_singles_dict(df.parent)
			if (
				refdoc.get(df.options) == doc.doctype
				and refdoc.get(df.fieldname) == doc.name
				and (
					# linked to an non-cancelled doc when deleting
					(method == "Delete" and not DocStatus(refdoc.docstatus).is_cancelled())
					# linked to a submitted doc when cancelling
					or (method == "Cancel" and not DocStatus(refdoc.docstatus).is_cancelled())
				)
			):
				raise_link_exists_exception(doc, df.parent, df.parent)
		else:
			# dynamic link in table
			df["table"] = ", `parent`, `parenttype`, `idx`" if meta.istable else ""
			for refdoc in frappe.db.sql(
				"""select `name`, `docstatus` {table} from `tab{parent}` where
				`{options}`=%s and `{fieldname}`=%s""".format(**df),
				(doc.doctype, doc.name),
				as_dict=True,
			):
				# linked to an non-cancelled doc when deleting
				# or linked to a submitted doc when cancelling
				if (method == "Delete" and not DocStatus(refdoc.docstatus).is_cancelled()) or (
					method == "Cancel" and not DocStatus(refdoc.docstatus).is_cancelled()
				):
					reference_doctype = refdoc.parenttype if meta.istable else df.parent
					reference_docname = refdoc.parent if meta.istable else refdoc.name

					if reference_doctype in frappe.get_hooks("ignore_links_on_delete") or (
						reference_doctype in ignore_linked_doctypes and method == "Cancel"
					):
						# don't check for communication and todo!
						continue

					at_position = f"at Row: {refdoc.idx}" if meta.istable else ""

					raise_link_exists_exception(doc, reference_doctype, reference_docname, at_position)