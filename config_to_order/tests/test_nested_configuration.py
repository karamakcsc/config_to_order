# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.api.variant_configuration import get_configuration_result

PARENT_CONFIG_DOCTYPE = "Test C2O Nested Parent Config"
SUB_CONFIG_DOCTYPE = "Test C2O Nested Sub Config"


def create_doctype_if_missing(name, fields):
	if frappe.db.exists("DocType", name):
		return
	frappe.get_doc({
		"doctype": "DocType",
		"name": name,
		"module": "Config To Order",
		"custom": 1,
		"naming_rule": "Random",
		"fields": fields,
		"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
	}).insert()


def create_test_item(item_code, **kwargs):
	if frappe.db.exists("Item", item_code):
		return frappe.get_doc("Item", item_code)
	doc = frappe.get_doc(dict(
		doctype="Item", item_code=item_code, item_name=item_code,
		item_group="All Item Groups", stock_uom="Nos", is_stock_item=1,
		**kwargs,
	))
	doc.insert()
	return doc


class TestNestedConfiguration(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			frappe.throw("No Company found - erpnext's before_tests setup did not run")

		create_doctype_if_missing(PARENT_CONFIG_DOCTYPE, [
			{"fieldname": "panel_config_name", "fieldtype": "Data", "label": "Panel Config Name"},
		])
		create_doctype_if_missing(SUB_CONFIG_DOCTYPE, [
			{"fieldname": "wire_qty", "fieldtype": "Float", "label": "Wire Qty"},
		])

		create_test_item("_Test C2O Nested Wire")
		create_test_item(
			"_Test C2O Nested Panel",
			is_configurable=1, configuration_doctype=SUB_CONFIG_DOCTYPE,
		)
		create_test_item(
			"_Test C2O Nested Laptop",
			is_configurable=1, configuration_doctype=PARENT_CONFIG_DOCTYPE,
		)

		if frappe.db.exists("BOM", {"item": "_Test C2O Nested Panel", "docstatus": 1}):
			cls.sub_bom_name = frappe.db.get_value(
				"BOM", {"item": "_Test C2O Nested Panel", "docstatus": 1}, "name")
		else:
			sub_bom = frappe.get_doc({
				"doctype": "BOM", "item": "_Test C2O Nested Panel", "quantity": 1, "company": cls.company,
				"items": [
					{"item_code": "_Test C2O Nested Wire", "qty": 1, "qty_from_configuration": "wire_qty"},
				],
			})
			sub_bom.insert()
			sub_bom.submit()
			cls.sub_bom_name = sub_bom.name

		if frappe.db.exists("BOM", {"item": "_Test C2O Nested Laptop", "docstatus": 1}):
			cls.bom_name = frappe.db.get_value(
				"BOM", {"item": "_Test C2O Nested Laptop", "docstatus": 1}, "name")
		else:
			bom = frappe.get_doc({
				"doctype": "BOM", "item": "_Test C2O Nested Laptop", "quantity": 1, "company": cls.company,
				"items": [
					{
						"item_code": "_Test C2O Nested Panel", "qty": 2,
						"sub_configuration_doctype": SUB_CONFIG_DOCTYPE,
						"sub_configuration_docname_field": "panel_config_name",
					},
				],
			})
			bom.insert()
			bom.submit()
			cls.bom_name = bom.name

	def get_args(self):
		return {
			"company": self.company, "doctype": "Sales Order", "name": "new-sales-order-1",
			"selling_price_list": "Standard Selling", "price_list_currency": "USD",
			"transaction_date": frappe.utils.nowdate(), "conversion_rate": 1.0,
			"plc_conversion_rate": 1.0, "ignore_pricing_rule": 1,
		}

	def test_sub_assembly_recurses_and_rolls_up_total(self):
		sub_config = frappe.get_doc({"doctype": SUB_CONFIG_DOCTYPE, "wire_qty": 7}).insert()
		parent_config = frappe.get_doc({
			"doctype": PARENT_CONFIG_DOCTYPE, "panel_config_name": sub_config.name,
		}).insert()

		result = get_configuration_result(
			self.bom_name, 0, PARENT_CONFIG_DOCTYPE, parent_config.name, self.get_args())

		panel_row = next(d for d in result.config_items if d.item_code == "_Test C2O Nested Panel")
		self.assertTrue(panel_row.nested_configuration_result)

		nested_result = frappe.get_doc("Configuration Result", panel_row.nested_configuration_result)
		self.assertEqual(nested_result.parent_configuration_result, result.name)
		self.assertEqual(nested_result.reference_doctype, SUB_CONFIG_DOCTYPE)
		self.assertEqual(nested_result.reference_docname, sub_config.name)

		wire_row = next(d for d in nested_result.config_items if d.item_code == "_Test C2O Nested Wire")
		self.assertEqual(wire_row.qty, 7)

		# parent row's rate/amount roll up from the nested result, not a flat item price lookup
		self.assertEqual(panel_row.rate, nested_result.total)
		self.assertEqual(panel_row.amount, nested_result.total * panel_row.qty)
		self.assertEqual(result.total, sum(d.amount for d in result.config_items))

	def test_missing_sub_configuration_falls_back_to_flat_item(self):
		# panel_config_name left blank - can't resolve a sub-configuration document,
		# so the component should resolve like an ordinary (non-nested) item instead of erroring
		parent_config = frappe.get_doc({
			"doctype": PARENT_CONFIG_DOCTYPE, "panel_config_name": None,
		}).insert()

		result = get_configuration_result(
			self.bom_name, 0, PARENT_CONFIG_DOCTYPE, parent_config.name, self.get_args())

		panel_row = next(d for d in result.config_items if d.item_code == "_Test C2O Nested Panel")
		self.assertFalse(panel_row.nested_configuration_result)

	def test_args_as_json_string_still_works_with_nesting(self):
		sub_config = frappe.get_doc({"doctype": SUB_CONFIG_DOCTYPE, "wire_qty": 3}).insert()
		parent_config = frappe.get_doc({
			"doctype": PARENT_CONFIG_DOCTYPE, "panel_config_name": sub_config.name,
		}).insert()

		result = get_configuration_result(
			self.bom_name, 0, PARENT_CONFIG_DOCTYPE, parent_config.name, json.dumps(self.get_args()))

		panel_row = next(d for d in result.config_items if d.item_code == "_Test C2O Nested Panel")
		self.assertTrue(panel_row.nested_configuration_result)
