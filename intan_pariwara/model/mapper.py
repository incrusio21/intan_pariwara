# Copyright (c) 2025, DAS and Contributors
# License: MIT. See LICENSE
import json
import frappe

@frappe.whitelist()
def map_docs(method, source_names, target_doc, args=None):
	'''Returns the mapped document calling the given mapper method
	with each of the given source docs on the target doc

	:param args: Args as string to pass to the mapper method
	E.g. args: "{ 'supplier': 'XYZ' }"'''

	for hook in reversed(frappe.get_hooks("override_whitelisted_methods", {}).get(method, [])):
		# override using the first hook
		method = hook
		break
	
	method = frappe.get_attr(method)
	if method not in frappe.whitelisted:
		raise frappe.PermissionError

	for src in json.loads(source_names):
		_args = (src, target_doc, json.loads(args)) if args else (src, target_doc)
		target_doc = method(*_args)
	return target_doc
