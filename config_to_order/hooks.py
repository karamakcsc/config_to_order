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
app_include_js = "/assets/js/config_to_order.min.js"

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
					'BOM Item-column_break_11',
					'BOM Item-configuration',
					'BOM Item-desc_from_configuration',
					'BOM Item-item_from_configuration',
					'BOM Item-qty_from_configuration',
					'BOM Item-selection_condition',
					'BOM-configuration_doctype',
					'Item-configuration_doctype',
					'Item-is_configurable',
					'Sales Order Item-config',
					'Sales Order Item-config_result',
					'Sales Order Item-configuration_docname',
					'Sales Order Item-configuration_doctype',
					'Sales Order Item-configuration_result',
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

from erpnext.manufacturing.doctype.bom import bom as _bom
from config_to_order.utils import check_selection_condition, get_qty_or_desc, get_bom_items_as_dict

_bom.get_bom_items_as_dict = get_bom_items_as_dict

from erpnext.manufacturing.doctype.bom.bom import BOM

def get_exploded_items(self):
	""" Get all raw materials including items from child bom"""
	self.cur_exploded_items = {}
	for d in self.get('items'):
		if d.bom_no:
			self.get_child_exploded_items(d.bom_no, d.stock_qty)
		else:
			self.add_to_cur_exploded_items(_frappe._dict({
				'item_code'		: d.item_code,
				'item_name'		: d.item_name,
				'operation'		: d.operation,
				'source_warehouse': d.source_warehouse,
				'description'	: d.description,
				'image'			: d.image,
				'stock_uom'		: d.stock_uom,
				'stock_qty'		: flt(d.stock_qty),
				'rate'			: d.base_rate,
				'selection_condition' : d.selection_condition,
				'item_from_configuration' : d.item_from_configuration,
				'qty_from_configuration' : d.qty_from_configuration,
				'desc_from_configuration' : d.desc_from_configuration,
				'include_item_in_manufacturing': d.include_item_in_manufacturing
			}))

BOM.get_exploded_items = get_exploded_items


def get_child_exploded_items(self, bom_no, stock_qty):
	""" Add all items from Flat BOM of child BOM"""
	# Did not use qty_consumed_per_unit in the query, as it leads to rounding loss
	child_fb_items = _frappe.db.sql("""select bom_item.item_code, bom_item.item_name,
			bom_item.description, bom_item.source_warehouse, bom_item.operation,
			bom_item.stock_uom, bom_item.stock_qty, bom_item.rate, bom_item.include_item_in_manufacturing,
			bom_item.stock_qty / ifnull(bom.quantity, 1) as qty_consumed_per_unit, bom_item.selection_condition,
			bom_item.item_from_configuration, bom_item.qty_from_configuration,bom_item.desc_from_configuration
			from `tabBOM Explosion Item` bom_item, tabBOM bom
			where bom_item.parent = bom.name and bom.name = %s and bom.docstatus = 1""", bom_no, as_dict=1)

	for d in child_fb_items:
		self.add_to_cur_exploded_items(_frappe._dict({
			'item_code'			: d['item_code'],
			'item_name'				: d['item_name'],
			'source_warehou'		: d['source_warehouse'],
			'operation'				: d['operation'],
			'description'			: d['description'],
			'stock_uom'				: d['stock_uom'],
			'stock_qty'				: d['qty_consumed_per_unit'] * stock_qty,
			'rate'					: flt(d['rate']),
			'selection_condition': d['selection_condition'],
			'item_from_configuration': d['item_from_configuration'],
			'qty_from_configuration': d['qty_from_configuration'],
			'desc_from_configuration': d['desc_from_configuration'],
			'include_item_in_manufacturing': d.get('include_item_in_manufacturing', 0)
		}))

BOM.get_child_exploded_items = get_child_exploded_items

from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder

def set_required_items(self, reset_only_qty=False):
	'''set required_items for production to keep track of reserved qty'''
	if not reset_only_qty:
		self.required_items = []

	if self.bom_no and self.qty:
		item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=self.qty,
			fetch_exploded = self.use_multi_level_bom)
		soi = _frappe.get_doc('Sales Order Item', self.sales_order_item) if self.sales_order_item else None
		configuration = _frappe.get_doc(soi.configuration_doctype, soi.configuration_docname) if soi and soi.configuration_docname else None

		if reset_only_qty:
			if not configuration:
				for d in self.get("required_items"):
					if item_dict.get(d.item_code):
						d.required_qty = item_dict.get(d.item_code).get("qty")
		else:
			# Attribute a big number (999) to idx for sorting putpose in case idx is NULL
			# For instance in BOM Explosion Item child table, the items coming from sub assembly items
			for item in sorted(item_dict.values(), key=lambda d: d['idx'] or 9999):
				if check_selection_condition(configuration, item):
					self.append('required_items', {
						'operation': item.operation,
						'item_code': item.item_code,
						'item_name': item.item_name,
						'supplier': item.supplier,
						'description': get_qty_or_desc(configuration, item, 'description', 'desc_from_configuration'),
						'required_qty': get_qty_or_desc(configuration, item, 'qty', 'qty_from_configuration'),
						'allow_alternative_item': item.allow_alternative_item,
						'source_warehouse': item.source_warehouse or item.default_warehouse,
						'include_item_in_manufacturing': item.include_item_in_manufacturing
					})
		self.set_available_qty()

WorkOrder.set_required_items = set_required_items
