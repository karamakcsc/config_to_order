# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe

from config_to_order.utils import validate_configuration_constraints


def validate(doc, method):
	"""Generic doc_events["*"] hook: only costs a query for doctypes with active constraints."""
	if not frappe.db.exists('Configuration Constraint', {'configuration_doctype': doc.doctype, 'is_active': 1}):
		return

	validate_configuration_constraints(doc)
