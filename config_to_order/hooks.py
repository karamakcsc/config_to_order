# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version
import frappe as _frappe
from frappe.utils import cstr, flt, getdate, comma_and, cint, nowdate, add_days

app_name = "config_to_order"
app_title = "Config To Order"
app_publisher = "Fisher"
app_description = "Config To Order"
app_icon = "octicon octicon-file-directory"
app_color = "blue"
app_email = "yuxinyong@163.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/config_to_order/css/config_to_order.css"
app_include_js = "config_to_order.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/config_to_order/css/config_to_order.css"
# web_include_js = "/assets/config_to_order/js/config_to_order.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
#doctype_js = {
#	"Item" : "public/js/item.js",
#	"BOM": "public/js/bom.js",
#	"Sales Order": "public/js/sales_order.js",
#	"Configuration Result": "public/js/configuration_result.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}
fixtures = [
    {
        "doctype": "DocType",
        "filters": [
            [
                "name",
                "in",
                [
                    'Configuration Result',
                    'Configuration Result Item',
                    'Configuration Constraint',
                    'computer',
                ],
            ]
        ],
    },
	{"doctype": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					'BOM Explosion Item-column_break_111',
					'BOM Explosion Item-configuration',
					'BOM Explosion Item-desc_from_configuration',
					'BOM Explosion Item-item_from_configuration',
					'BOM Explosion Item-qty_from_configuration',
					'BOM Explosion Item-selection_condition',
					'BOM Explosion Item-sub_configuration_doctype',
					'BOM Explosion Item-sub_configuration_docname_field',
					'BOM Explosion Item-price_formula',
					'BOM Item-column_break_11',
					'BOM Item-configuration',
					'BOM Item-desc_from_configuration',
					'BOM Item-item_from_configuration',
					'BOM Item-qty_from_configuration',
					'BOM Item-selection_condition',
					'BOM Item-sub_configuration_doctype',
					'BOM Item-sub_configuration_docname_field',
					'BOM Item-price_formula',
					'BOM-configuration_doctype',
					'Item-configuration_doctype',
					'Item-is_configurable',
					'Sales Order Item-config',
					'Sales Order Item-config_result',
					'Sales Order Item-configuration_docname',
					'Sales Order Item-configuration_doctype',
					'Sales Order Item-configuration_result',
					'Quotation Item-configuration_section',
					'Quotation Item-configuration_doctype',
					'Quotation Item-configuration_docname',
					'Quotation Item-config',
					'Quotation Item-configuration_column',
					'Quotation Item-configuration_result',
					'Quotation Item-config_result',
					'Serial No-configuration_result',
				],
			]
		],
	},
]
# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "config_to_order.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "config_to_order.install.before_install"
# after_install = "config_to_order.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "config_to_order.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"BOM": {
		"validate": "config_to_order.doc_events.bom.validate"
	},
	"Sales Order":{
		"on_trash": "config_to_order.doc_events.sales_order.delete_configuration_doc"
	},
	"Serial and Batch Bundle": {
		"on_submit": "config_to_order.doc_events.serial_and_batch_bundle.on_submit"
	},
	"*": {
		"validate": "config_to_order.doc_events.configuration.validate"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"config_to_order.tasks.all"
# 	],
# 	"daily": [
# 		"config_to_order.tasks.daily"
# 	],
# 	"hourly": [
# 		"config_to_order.tasks.hourly"
# 	],
# 	"weekly": [
# 		"config_to_order.tasks.weekly"
# 	]
# 	"monthly": [
# 		"config_to_order.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "config_to_order.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "config_to_order.event.get_events"
# }

import inspect

from erpnext.manufacturing.doctype.bom import bom as _bom
from config_to_order.utils import (
	check_selection_condition, get_qty_or_desc, get_bom_items_as_dict, CONFIGURATION_FIELDS,
	_lookup_by_item_and_operation,
)

_bom.get_bom_items_as_dict = get_bom_items_as_dict

from erpnext.manufacturing.doctype.bom.bom import BOM

# These wrap erpnext's own BOM explosion logic (rather than reimplementing it) so rate
# calculation, is_sub_assembly_item/sourced_by_supplier handling, etc. always match the
# installed erpnext version - they only need to carry the configuration-specific custom
# fields (selection_condition, item_from_configuration, ...) into the Flat BOM alongside
# whatever erpnext itself already computes.

_original_get_exploded_items = BOM.get_exploded_items

def get_exploded_items(self):
	_original_get_exploded_items(self)
	for d in self.get('items'):
		if d.bom_no:
			continue
		entry = _lookup_by_item_and_operation(self.cur_exploded_items, d.item_code, d.operation)
		if entry:
			for field in CONFIGURATION_FIELDS:
				entry[field] = d.get(field)

BOM.get_exploded_items = get_exploded_items


_original_get_child_exploded_items = BOM.get_child_exploded_items
# erpnext v15's get_child_exploded_items doesn't take an `operation` arg (added in v16) -
# detect what the installed version actually accepts instead of hardcoding a version.
_get_child_exploded_items_supports_operation = (
	'operation' in inspect.signature(_original_get_child_exploded_items).parameters
)

def get_child_exploded_items(self, bom_no, stock_qty, operation=None):
	if _get_child_exploded_items_supports_operation:
		_original_get_child_exploded_items(self, bom_no, stock_qty, operation)
	else:
		_original_get_child_exploded_items(self, bom_no, stock_qty)

	fields = ", ".join("bom_item." + f for f in CONFIGURATION_FIELDS)
	child_fb_items = _frappe.db.sql("""select bom_item.item_code, bom_item.operation, {fields}
		from `tabBOM Explosion Item` bom_item, `tabBOM` bom
		where bom_item.parent = bom.name and bom.name = %s and bom.docstatus = 1""".format(fields=fields),
		bom_no, as_dict=1)

	for d in child_fb_items:
		entry = _lookup_by_item_and_operation(self.cur_exploded_items, d.item_code, d.operation or operation)
		if entry:
			for field in CONFIGURATION_FIELDS:
				entry[field] = d.get(field)

BOM.get_child_exploded_items = get_child_exploded_items

from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder

_original_set_required_items = WorkOrder.set_required_items
# erpnext v15's set_required_items doesn't take a `reset_source_warehouse` arg (added in v16).
_set_required_items_supports_reset_source_warehouse = (
	'reset_source_warehouse' in inspect.signature(_original_set_required_items).parameters
)

def set_required_items(self, reset_only_qty=False, reset_source_warehouse=False):
	'''After erpnext builds required_items from the BOM, drop rows the active Configuration
	Result excludes (via selection_condition/item_from_configuration) and let the
	configuration override description/qty where it specifies its own.'''
	if _set_required_items_supports_reset_source_warehouse:
		_original_set_required_items(self, reset_only_qty=reset_only_qty, reset_source_warehouse=reset_source_warehouse)
	else:
		_original_set_required_items(self, reset_only_qty=reset_only_qty)

	if not (self.bom_no and self.qty):
		return

	soi = _frappe.get_doc('Sales Order Item', self.sales_order_item) if self.sales_order_item else None
	configuration = _frappe.get_doc(soi.configuration_doctype, soi.configuration_docname) if soi and soi.configuration_docname else None
	if not configuration:
		return

	item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=self.qty,
		fetch_exploded=self.use_multi_level_bom)

	def lookup(d):
		return item_dict.get((d.item_code, d.operation)) or item_dict.get(d.item_code)

	if reset_only_qty:
		for d in self.get("required_items"):
			item = lookup(d)
			if item:
				d.required_qty = get_qty_or_desc(configuration, item, 'qty', 'qty_from_configuration')
		return

	kept = []
	for d in self.get("required_items"):
		item = lookup(d)
		if item and not check_selection_condition(configuration, item):
			continue
		if item:
			d.description = get_qty_or_desc(configuration, item, 'description', 'desc_from_configuration')
			d.required_qty = get_qty_or_desc(configuration, item, 'qty', 'qty_from_configuration')
			d.amount = flt(d.rate) * flt(d.required_qty)
		kept.append(d)
	self.required_items = kept
	self.set_available_qty()

WorkOrder.set_required_items = set_required_items
