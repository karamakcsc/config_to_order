# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import json
import frappe.utils
from frappe.utils import cstr, flt, getdate, comma_and, cint, nowdate, add_days
from frappe import _
from erpnext.stock.get_item_details import get_item_details

from config_to_order.utils import check_selection_condition, get_qty_or_desc, get_bom_items_as_dict

MAX_SUB_CONFIGURATION_DEPTH = 10

@frappe.whitelist()
def get_configuration_result(bom_no, fetch_exploded, configuration_doctype, configuration_docname, args = {}):
    '''set required_items for production to keep track of reserved qty
    args "company" : args.get('company'),
            "customer": args.get('customer'),
            "conversion_rate": args.get('conversion_rate') or 1.0,
            "selling_price_list": args.get('selling_price_list'),
            "price_list_currency": args.get('price_list_currency'),
            "plc_conversion_rate": args.get('plc_conversion_rate') or 1.0,
            "doctype": args.get('doctype'),
            "name": args.get('name'),
            "transaction_date": args.get('transaction_date'),
            "ignore_pricing_rule": args.get('ignore_pricing_rule'),
            "project": args.get('project')
    '''
    args = frappe._dict(json.loads(args) if isinstance(args, str) else args)
    return _resolve_configuration_result(bom_no, fetch_exploded, configuration_doctype, configuration_docname, args)


def _resolve_configuration_result(bom_no, fetch_exploded, configuration_doctype, configuration_docname, args,
	parent_configuration_result=None, _depth=0):
    '''Recursive worker behind get_configuration_result. Not whitelisted - args is always a dict here.'''
    if _depth > MAX_SUB_CONFIGURATION_DEPTH:
        frappe.throw(_("Sub-assembly configuration nested too deep (possible cycle) at {0} levels").format(_depth))

    def update_item_detail(item_code, config_item):
        args.update({"item_code": item_code})
        item_detail = get_item_details(args)
        for field in ['valuation_rate', 'pricing_rule', 'discount_percentage', 'discount_amount', 'price_list_rate',
                      'stock_qty','uom']:
            config_item.update({field: item_detail.get(field)})
        config_item.update({'rate': item_detail.get('rate') or config_item.get('price_list_rate') or 0})
        config_item.update({'amount': config_item.get('rate') * config_item.get('qty')})

    def apply_price_formula(item, config_item):
        '''If `item` declares a price_formula, evaluate it (doc=configuration, qty=resolved qty)
        and use the result as this row's per-unit rate instead of the plain item price.'''
        price_formula = item.get('price_formula')
        if not price_formula:
            return

        rate = flt(frappe.safe_eval(price_formula, None, {'doc': configuration, 'qty': config_item.get('qty')}))
        config_item.update({'rate': rate, 'amount': rate * config_item.get('qty')})

    def resolve_sub_configuration(item, config_item):
        '''If `item` is itself a configurable sub-assembly, recursively resolve its own Super BOM
        and roll its total up into config_item's rate/amount instead of a plain item price lookup.'''
        sub_configuration_doctype = item.get('sub_configuration_doctype')
        sub_docname_field = item.get('sub_configuration_docname_field')
        if not (sub_configuration_doctype and sub_docname_field):
            return

        sub_configuration_docname = configuration.get(sub_docname_field)
        if not sub_configuration_docname:
            return

        sub_bom_no = frappe.db.get_value(
            'BOM', {'item': item.item_code, 'is_default': 1, 'docstatus': 1}, 'name')
        if not sub_bom_no:
            return

        nested_result = _resolve_configuration_result(
            sub_bom_no, fetch_exploded, sub_configuration_doctype, sub_configuration_docname, args,
            parent_configuration_result=configuration_result.name, _depth=_depth + 1)

        if frappe.db.exists('Configuration Result', nested_result.name):
            frappe.delete_doc('Configuration Result', nested_result.name, force=1, ignore_permissions=True)
        # parent_configuration_result points at the top-level result, which by design stays
        # unsaved server-side (the client persists it later) - skip link validation for that.
        nested_result.flags.ignore_links = True
        nested_result.insert(ignore_permissions=True)

        config_item.update({
            'nested_configuration_result': nested_result.name,
            'rate': nested_result.total,
            'amount': nested_result.total * config_item.get('qty'),
        })

    item_dict = get_bom_items_as_dict(bom_no, args.get('company'), qty = 1, fetch_exploded = fetch_exploded)

    configuration = frappe.get_doc(configuration_doctype, configuration_docname)
    configuration_result = frappe.new_doc('Configuration Result')
    configuration_result.reference_doctype = configuration_doctype
    configuration_result.reference_docname = configuration_docname
    configuration_result.parent_configuration_result = parent_configuration_result
    # snapshot the configuration's field values now, so later edits to the Configuration
    # Template's fields (or the document itself) don't retroactively reinterpret this result
    configuration_result.configuration_snapshot = frappe.as_json(configuration.as_dict())
    configuration_result.set_new_name()
    for item in sorted(item_dict.values(), key=lambda d: d['idx'] or 9999):
        if check_selection_condition(configuration, item):
            config_item = {
                'item_code': item.item_code,
                'item_name': item.item_name,
                'description': get_qty_or_desc(configuration, item, 'description', 'desc_from_configuration'),
                'qty': get_qty_or_desc(configuration, item, 'qty', 'qty_from_configuration')
            }
            update_item_detail(item.item_code, config_item)
            apply_price_formula(item, config_item)
            resolve_sub_configuration(item, config_item)
            configuration_result.append('config_items', config_item )

    configuration_result.total = sum(flt(d.amount) for d in configuration_result.config_items)
    return configuration_result

@frappe.whitelist()
def get_configuration_fields(doctype=None, txt=None, searchfield=None, start=None, page_len=None, filters=None):
	"""get relevant fields of the configuration doctype"""

	def check(f):
		return not txt or [t for t in [f.fieldname,f.label,_(f.fieldname), _(f.label)] if txt in t]

	filters = filters or {}
	fields = []
	doctype = filters.get('configuration_doctype')
	field_types = filters.get('field_types', [])
	if doctype:
		meta = frappe.get_meta(doctype)
		fields = [[f.fieldname, _(f.fieldname), _(f.label)] for f in meta.fields if (not field_types or f.fieldtype in field_types) and check(f)]

	return fields

@frappe.whitelist()
def get_sub_configuration_requirements(bom_no):
	"""BOM Item rows of bom_no that are themselves configurable sub-assemblies.

	Used by the client to prompt for a sub-configuration document per such row
	before calling get_configuration_result.
	"""
	return frappe.db.sql("""select item_code, sub_configuration_doctype, sub_configuration_docname_field
		from `tabBOM Item`
		where parent = %(bom_no)s and docstatus < 2 and ifnull(sub_configuration_doctype, '') != ''""",
		{'bom_no': bom_no}, as_dict=True)

@frappe.whitelist()
def get_configuration_docname(doctype=None, txt=None, searchfield=None, start=None, page_len=None, filters=None):
	"""get relevant fields of the configuration doctype"""

	filters = filters or {}
	source_doctype = filters.get('source_doctype') or 'Sales Order Item'

	if source_doctype == 'Sales Order Item':
		# kept as its own literal query so this, the original/default path, is untouched
		return frappe.db.sql("""select soi.configuration_docname, so.name, so.customer from `tabSales Order Item` soi
			inner join `tabSales Order` so on soi.parent=so.name where
			soi.configuration_doctype = %(configuration_doctype)s  and soi.configuration_docname is not null
			and (soi.configuration_docname like %(txt)s or so.name like %(txt)s)""",
			{'configuration_doctype':filters.get('configuration_doctype'),
			 'txt': "%%%s%%" % txt})

	# generic path for any other source doctype (e.g. Quotation Item): find its parent via the
	# Table docfield that links them, rather than hardcoding a doctype->parent map
	parent_doctype = frappe.db.get_value('DocField', {'fieldtype': 'Table', 'options': source_doctype}, 'parent')
	if not parent_doctype:
		frappe.throw(_("Could not determine the parent doctype for {0}").format(source_doctype))

	# both are confirmed real, installed doctypes at this point (get_meta throws otherwise) -
	# safe to interpolate into the query below as table names
	frappe.get_meta(source_doctype)
	frappe.get_meta(parent_doctype)

	return frappe.db.sql("""select child.configuration_docname, parent.name, '' as customer
		from `tab{source_doctype}` child
		inner join `tab{parent_doctype}` parent on child.parent = parent.name
		where child.configuration_doctype = %(configuration_doctype)s and child.configuration_docname is not null
		and (child.configuration_docname like %(txt)s or parent.name like %(txt)s)""".format(
			source_doctype=source_doctype, parent_doctype=parent_doctype),
		{'configuration_doctype': filters.get('configuration_doctype'), 'txt': "%%%s%%" % txt})
