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
    def update_item_detail(item_code, config_item):
        args.update({"item_code": item_code})
        item_detail = get_item_details(args)
        for field in ['valuation_rate', 'pricing_rule', 'discount_percentage', 'discount_amount', 'price_list_rate',
                      'stock_qty','uom']:
            config_item.update({field: item_detail.get(field)})
        config_item.update({'rate': item_detail.get('rate') or config_item.get('price_list_rate') or 0})
        config_item.update({'amount': config_item.get('rate') * config_item.get('qty')})

    args = frappe._dict(json.loads(args) if isinstance(args, str) else args)
    item_dict = get_bom_items_as_dict(bom_no, args.get('company'), qty = 1, fetch_exploded = fetch_exploded)

    configuration = frappe.get_doc(configuration_doctype, configuration_docname)
    configuration_result = frappe.new_doc('Configuration Result')
    configuration_result.reference_doctype = configuration_doctype
    configuration_result.reference_docname = configuration_docname
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
            configuration_result.append('config_items', config_item )
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
def get_configuration_docname(doctype=None, txt=None, searchfield=None, start=None, page_len=None, filters=None):
	"""get relevant fields of the configuration doctype"""

	filters = filters or {}
	return frappe.db.sql("""select soi.configuration_docname, so.name, so.customer from `tabSales Order Item` soi
		inner join `tabSales Order` so on soi.parent=so.name where
		soi.configuration_doctype = %(configuration_doctype)s  and soi.configuration_docname is not null
		and (soi.configuration_docname like %(txt)s or so.name like %(txt)s)""",
		{'configuration_doctype':filters.get('configuration_doctype'),
		 'txt': "%%%s%%" % txt})
