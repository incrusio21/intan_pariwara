# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from erpnext.accounts.doctype.pos_profile.pos_profile import get_child_nodes

class POEProfile(Document):
	pass

def get_item_groups(pos_profile):
	item_groups = []
	pos_profile = frappe.get_cached_doc("POE Profile", pos_profile)

	if pos_profile.get("item_groups"):
		# Get items based on the item groups defined in the POS profile
		for data in pos_profile.get("item_groups"):
			item_groups.extend(
				["%s" % frappe.db.escape(d.name) for d in get_child_nodes("Item Group", data.item_group)]
			)

	return list(set(item_groups))

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def poe_profile_query(doctype, txt, searchfield, start, page_len, filters):
	user = frappe.session["user"]
	company = filters.get("company") or frappe.defaults.get_user_default("company")

	args = {
		"user": user,
		"start": start,
		"company": company,
		"page_len": page_len,
		"txt": "%%%s%%" % txt,
	}

	pos_profile = frappe.db.sql(
		"""select pf.name
		from
			`tabPOE Profile` pf, `tabPOE Profile User` pfu
		where
			pfu.parent = pf.name and pfu.user = %(user)s and pf.company = %(company)s
			and (pf.name like %(txt)s)
			and pf.disabled = 0 limit %(page_len)s offset %(start)s""",
		args,
	)

	if not pos_profile:
		del args["user"]

		pos_profile = frappe.db.sql(
			"""select pf.name
			from
				`tabPOE Profile` pf left join `tabPOE Profile User` pfu
			on
				pf.name = pfu.parent
			where
				ifnull(pfu.user, '') = ''
				and pf.company = %(company)s
				and pf.name like %(txt)s
				and pf.disabled = 0""",
			args,
		)

	return pos_profile