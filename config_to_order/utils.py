# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import flt, cint
from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict as _core_get_bom_items_as_dict

CONFIGURATION_FIELDS = [
	'selection_condition', 'item_from_configuration', 'qty_from_configuration',
	'desc_from_configuration', 'sub_configuration_doctype', 'sub_configuration_docname_field',
	'price_formula',
]


def check_selection_condition(configuration, bom_item):
	"""Return True if bom_item should be included for the given configuration."""
	selection_condition = bom_item.get('selection_condition')
	item_from_configuration = bom_item.get('item_from_configuration')

	if not configuration or not (item_from_configuration or selection_condition):
		return True
	elif item_from_configuration:
		return configuration.get(item_from_configuration) == bom_item.item_code
	elif selection_condition:
		return frappe.safe_eval(selection_condition, None, {'doc': configuration})

	return False


def get_qty_or_desc(configuration, bom_item, bom_field, config_field):
	"""Resolve qty/description: use configuration's override field, falling back to the BOM value."""
	config_field = bom_item.get(config_field)
	if not configuration or not config_field:
		return bom_item.get(bom_field)

	return configuration.get(config_field) or bom_item.get(bom_field)


def get_bom_items_as_dict(bom, company, qty=1, fetch_exploded=1, fetch_secondary_items=0,
	include_non_stock_items=False, fetch_qty_in_stock_uom=True):
	"""Delegates to erpnext's own get_bom_items_as_dict (so rate/warehouse/phantom-item/etc
	logic always matches the installed erpnext version), then enriches each row with the
	configuration-specific custom fields (selection_condition, item_from_configuration, ...)
	that erpnext's own query doesn't select, keyed by (item_code[, operation])."""
	item_dict = _core_get_bom_items_as_dict(
		bom, company, qty=qty, fetch_exploded=fetch_exploded, fetch_secondary_items=fetch_secondary_items,
		include_non_stock_items=include_non_stock_items, fetch_qty_in_stock_uom=fetch_qty_in_stock_uom,
	)
	if not item_dict:
		return item_dict

	if fetch_secondary_items:
		table = "BOM Secondary Item"
	elif cint(fetch_exploded):
		table = "BOM Explosion Item"
	else:
		table = "BOM Item"

	rows = frappe.db.sql("""select item_code, operation, {fields}
		from `tab{table}`
		where parent = %(bom)s and docstatus < 2""".format(
			table=table, fields=", ".join(CONFIGURATION_FIELDS)),
		{'bom': bom}, as_dict=True)

	for row in rows:
		key = (row.item_code, row.operation) if row.operation else row.item_code
		item = item_dict.get(key)
		if item:
			for field in CONFIGURATION_FIELDS:
				item[field] = row.get(field)

	return item_dict


CONSTRAINT_FIELDS = [
	'name', 'constraint_type', 'message',
	'if_field', 'if_operator', 'if_value',
	'then_field', 'then_operator', 'then_value',
	'range_field', 'min_value', 'max_value',
	'expression',
]


def get_active_constraints(configuration_doctype):
	"""Active Configuration Constraint rows registered against configuration_doctype."""
	return frappe.get_all(
		'Configuration Constraint',
		filters={'configuration_doctype': configuration_doctype, 'is_active': 1},
		fields=CONSTRAINT_FIELDS,
	)


def _matches(configuration, field, operator, value):
	"""Whether configuration.get(field) satisfies `operator value` (e.g. '>=' '5')."""
	if not field:
		return True

	actual = configuration.get(field)

	if operator in ('>', '>=', '<', '<='):
		if actual is None or actual == '':
			return False
		try:
			actual_num, target_num = float(actual), float(value)
		except (TypeError, ValueError):
			return False
		if operator == '>':
			return actual_num > target_num
		if operator == '>=':
			return actual_num >= target_num
		if operator == '<':
			return actual_num < target_num
		return actual_num <= target_num

	actual_str = '' if actual is None else str(actual)
	if operator == 'in':
		return actual_str in [v.strip() for v in (value or '').split(',')]
	if operator == 'not in':
		return actual_str not in [v.strip() for v in (value or '').split(',')]

	target_str = '' if value is None else str(value)
	if operator == '!=':
		return actual_str != target_str
	return actual_str == target_str


def evaluate_constraint(configuration, constraint):
	"""Return True if `configuration` satisfies `constraint` (a Configuration Constraint row), False if violated."""
	constraint_type = constraint.get('constraint_type')

	if constraint_type in ('Requires', 'Excludes'):
		if not _matches(configuration, constraint.get('if_field'), constraint.get('if_operator'), constraint.get('if_value')):
			return True
		then_matches = _matches(configuration, constraint.get('then_field'), constraint.get('then_operator'), constraint.get('then_value'))
		return then_matches if constraint_type == 'Requires' else not then_matches

	if constraint_type == 'Range':
		value = configuration.get(constraint.get('range_field'))
		if value is None or value == '':
			return True
		try:
			value_num = float(value)
		except (TypeError, ValueError):
			return True
		min_value, max_value = constraint.get('min_value'), constraint.get('max_value')
		if min_value is not None and value_num < float(min_value):
			return False
		if max_value is not None and value_num > float(max_value):
			return False
		return True

	if constraint_type == 'Expression':
		return bool(frappe.safe_eval(constraint.get('expression'), None, {'doc': configuration}))

	return True


def validate_configuration_constraints(configuration):
	"""frappe.throw on the first active Configuration Constraint violated by `configuration`."""
	for constraint in get_active_constraints(configuration.doctype):
		if not evaluate_constraint(configuration, constraint):
			frappe.throw(
				constraint.get('message') or _("Configuration violates constraint {0} ({1})").format(
					constraint.get('name'), constraint.get('constraint_type')),
				title=_("Invalid Configuration"),
			)
