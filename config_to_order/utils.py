# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import flt, cint


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


def get_bom_items_as_dict(bom, company, qty=1, fetch_exploded=1, fetch_scrap_items=0,
	include_non_stock_items=False, fetch_qty_in_stock_uom=True):
	item_dict = {}

	# Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
	query = """select
				bom_item.item_code,
				bom_item.idx,
				item.item_name,
				sum(bom_item.{qty_field}/ifnull(bom.quantity, 1)) * %(qty)s as qty,
				item.description,
				item.image,
				item.stock_uom,
				item.allow_alternative_item,
				item_default.default_warehouse,
				item_default.expense_account as expense_account,
				item_default.buying_cost_center as cost_center
				{select_columns}
			from
				`tab{table}` bom_item
				JOIN `tabBOM` bom ON bom_item.parent = bom.name
				JOIN `tabItem` item ON item.name = bom_item.item_code
				LEFT JOIN `tabItem Default` item_default
					ON item_default.parent = item.name and item_default.company = %(company)s
			where
				bom_item.docstatus < 2
				and bom.name = %(bom)s
				and item.is_stock_item in (1, {is_stock_item})
				{where_conditions}
				group by item_code, stock_uom {groupby_columns}
				order by idx"""

	is_stock_item = 0 if include_non_stock_items else 1
	if cint(fetch_exploded):
		query = query.format(table="BOM Explosion Item",
			where_conditions="",
			is_stock_item=is_stock_item,
			qty_field="stock_qty",
			select_columns = """, bom_item.source_warehouse, bom_item.operation, bom_item.include_item_in_manufacturing,
				(Select idx from `tabBOM Item` where item_code = bom_item.item_code and parent = %(parent)s limit 1) as idx,
				  bom_item.selection_condition, bom_item.item_from_configuration, bom_item.qty_from_configuration,
				  bom_item.desc_from_configuration, bom_item.sub_configuration_doctype, bom_item.sub_configuration_docname_field, bom_item.price_formula""",
			groupby_columns = """, bom_item.operation""")

		items = frappe.db.sql(query, { "parent": bom, "qty": qty, "bom": bom, "company": company }, as_dict=True)
	elif fetch_scrap_items:
		query = query.format(table="BOM Scrap Item", where_conditions="", select_columns=", bom_item.idx", is_stock_item=is_stock_item, qty_field="stock_qty", groupby_columns="")
		items = frappe.db.sql(query, { "qty": qty, "bom": bom, "company": company }, as_dict=True)
	else:
		query = query.format(table="BOM Item", where_conditions="", is_stock_item=is_stock_item,
			qty_field="stock_qty" if fetch_qty_in_stock_uom else "qty",
			select_columns = """, bom_item.uom, bom_item.conversion_factor, bom_item.source_warehouse, bom_item.idx,
							bom_item.operation, bom_item.include_item_in_manufacturing,
							bom_item.selection_condition, bom_item.item_from_configuration, bom_item.qty_from_configuration,
			  			bom_item.desc_from_configuration, bom_item.sub_configuration_doctype, bom_item.sub_configuration_docname_field, bom_item.price_formula""",
			groupby_columns = """, bom_item.operation""")
		items = frappe.db.sql(query, { "qty": qty, "bom": bom, "company": company }, as_dict=True)

	for item in items:
		key = (item.item_code)
		if item.operation:
			key = (item.item_code, item.operation)

		if key in item_dict:
			item_dict[key]["qty"] += flt(item.qty)
		else:
			item_dict[key] = item

	for item, item_details in item_dict.items():
		for d in [["Account", "expense_account", "stock_adjustment_account"],
			["Cost Center", "cost_center", "cost_center"], ["Warehouse", "default_warehouse", ""]]:
				company_in_record = frappe.db.get_value(d[0], item_details.get(d[1]), "company")
				if not item_details.get(d[1]) or (company_in_record and company != company_in_record):
					item_dict[item][d[1]] = frappe.get_cached_value('Company',  company,  d[2]) if d[2] else None

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
