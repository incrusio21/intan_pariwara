# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe import _, cstr
from frappe.query_builder import DocType
from frappe.utils import cint, now_datetime
from collections.abc import Callable
from typing import Optional

from frappe.model.document import Document
from frappe.model.naming import (
    NAMING_SERIES_PATTERN, InvalidNamingSeriesError, 
	parse_naming_series
)

class CustomerSeries(Document):
	pass

class NamingSeries:
	__slots__ = ("jenis_relasi", "kode_kab", "name", "series")

	def __init__(self, jenis_relasi: str, kode_kab: str, key: str):
		self.jenis_relasi = jenis_relasi
		self.kode_kab = kode_kab
		self.name = ""
		
		inisial = frappe.get_cached_value("Jenis Relasi", jenis_relasi, ["customer_inisial", "series_digit"], as_dict=1)
		if not inisial or not inisial.customer_inisial:
			return 
		
		self.name = inisial.customer_inisial + kode_kab + key
		self.series = self.name + "." + ("#" * (inisial.series_digit or 4))

	def validate(self):
		if not self.name:
			frappe.throw(
				_("Naming Series Is Missing"),
				exc=InvalidNamingSeriesError,
			)

		if "." not in self.series:
			frappe.throw(
				_("Invalid naming series {}: dot (.) missing").format(frappe.bold(self.series)),
				exc=InvalidNamingSeriesError,
			)

		if not NAMING_SERIES_PATTERN.match(self.series):
			frappe.throw(
				_(
					"Special Characters except '-', '#', '.', '/', '{{' and '}}' not allowed in naming series {0}"
				).format(frappe.bold(self.series)),
				exc=InvalidNamingSeriesError,
			)

	def generate_next_name(self, doc: "Document", *, ignore_validate=False) -> str:
		if not ignore_validate:
			self.validate()

		
		parts = self.series.split(".")
		series = parse_naming_series(parts, doc=doc, number_generator=getseries)
		
		self.set_fixed_field()
		
		return series

	def set_fixed_field(self):
		cs = frappe.get_doc("Customer Series", self.name)
		
		cs.jenis_relasi = self.jenis_relasi
		cs.kode_kab = self.kode_kab
		cs.save()

	def get_prefix(self) -> str:
		"""Naming series stores prefix to maintain a counter in DB. This prefix can be used to update counter or validations.

		e.g. `SINV-.YY.-.####` has prefix of `SINV-22-` in database for year 2022.
		"""

		prefix = None

		def fake_counter_backend(partial_series, digits):
			nonlocal prefix
			prefix = partial_series
			return "#" * digits

		# This function evaluates all parts till we hit numerical parts and then
		# sends prefix + digits to DB to find next number.
		# Instead of reimplementing the whole parsing logic in multiple places we
		# can just ask this function to give us the prefix.
		parse_naming_series(self.series, number_generator=fake_counter_backend)

		if prefix is None:
			frappe.throw(_("Invalid Naming Series: {}").format(self.series))

		return prefix

	def get_preview(self, doc=None) -> list[str]:
		"""Generate preview of naming series without using DB counters"""
		generated_names = []
		for count in range(1, 4):

			def fake_counter(_prefix, digits):
				# ignore B023: binding `count` is not necessary because
				# function is evaluated immediately and it can not be done
				# because of function signature requirement
				return str(count).zfill(digits)

			generated_names.append(parse_naming_series(self.series, doc=doc, number_generator=fake_counter))
		return generated_names

	def update_counter(self, new_count: int) -> None:
		"""Warning: Incorrectly updating series can result in unusable transactions"""
		Series = frappe.qb.DocType("Customer Series")
		prefix = self.get_prefix()

		# Initialize if not present in DB
		if frappe.db.get_value("Customer Series", prefix, "name", order_by="name") is None:
			frappe.qb.into(Series).insert(prefix, 0).columns("name", "current").run()

		(frappe.qb.update(Series).set(Series.current, cint(new_count)).where(Series.name == prefix)).run()

	def get_current_value(self) -> int:
		prefix = self.get_prefix()
		return cint(frappe.db.get_value("Customer Series", prefix, "current", order_by="name"))

def make_autoname(jenis_relasi, doc="", *, ignore_validate=False):
	"""
	     Creates an autoname from the given key:

	     **Autoname rules:**

	              * The key is separated by '.'
	              * '####' represents a series. The string before this part becomes the prefix:
	                     Example: ABC.#### creates a series ABC0001, ABC0002 etc
	              * 'MM' represents the current month
	              * 'YY' and 'YYYY' represent the current year


	*Example:*

	              * DE./.YY./.MM./.##### will create a series like
	                DE/09/01/00001 where 09 is the year, 01 is the month and 00001 is the series
	"""

	key = ""
	if jenis_relasi  == "Instansi":
		key +=  doc.kode_instansi + doc.kode_bidangsatker

	series = NamingSeries(jenis_relasi, doc.kode_kab, key)
	if not series.name:
		return
	
	return series.generate_next_name(doc, ignore_validate=ignore_validate)

def getseries(key, digits):
	# series created ?
	# Using frappe.qb as frappe.get_values does not allow order_by=None
	series = DocType("Customer Series")
	current = (frappe.qb.from_(series).where(series.name == key).for_update().select("current")).run()

	if current and current[0][0] is not None:
		current = current[0][0]
		# yes, update it
		frappe.db.sql("UPDATE `tabCustomer Series` SET `current` = `current` + 1 WHERE `name`=%s", (key,))
		current = cint(current) + 1
	else:
		# no, create it
		frappe.db.sql("INSERT INTO `tabCustomer Series` (`name`, `current`) VALUES (%s, 1)", (key,))
		current = 1
	return ("%0" + str(digits) + "d") % current