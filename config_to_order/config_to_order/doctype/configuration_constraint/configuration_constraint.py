# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document

STRUCTURED_FIELDS = ('if_field', 'if_operator', 'if_value', 'then_field', 'then_operator', 'then_value')


class ConfigurationConstraint(Document):
	def validate(self):
		self.validate_required_fields()
		self.validate_referenced_fields()
		if self.constraint_type == 'Expression':
			self.validate_expression()

	def validate_required_fields(self):
		if self.constraint_type in ('Requires', 'Excludes'):
			for fieldname in STRUCTURED_FIELDS:
				if not self.get(fieldname):
					frappe.throw(_("{0} is required for a {1} constraint").format(
						_(self.meta.get_field(fieldname).label), self.constraint_type))
		elif self.constraint_type == 'Range':
			if not self.range_field:
				frappe.throw(_("Range Field is required for a Range constraint"))
			if self.min_value is None and self.max_value is None:
				frappe.throw(_("Set at least one of Min Value or Max Value for a Range constraint"))
		elif self.constraint_type == 'Expression':
			if not self.expression:
				frappe.throw(_("Expression is required for an Expression constraint"))

	def validate_referenced_fields(self):
		if not self.configuration_doctype:
			return

		meta = frappe.get_meta(self.configuration_doctype)
		if self.constraint_type in ('Requires', 'Excludes'):
			field_refs = [('if_field', self.if_field), ('then_field', self.then_field)]
		elif self.constraint_type == 'Range':
			field_refs = [('range_field', self.range_field)]
		else:
			field_refs = []

		for label_fieldname, referenced_fieldname in field_refs:
			if referenced_fieldname and not meta.get_field(referenced_fieldname):
				frappe.throw(_("{0}: {1} is not a valid field in configuration doctype {2}").format(
					_(self.meta.get_field(label_fieldname).label), referenced_fieldname, self.configuration_doctype))

	def validate_expression(self):
		try:
			dummy_configuration = frappe.new_doc(self.configuration_doctype)
			frappe.safe_eval(self.expression, None, {'doc': dummy_configuration})
		except Exception as e:
			frappe.throw(_("Invalid expression: {0}").format(str(e)))
