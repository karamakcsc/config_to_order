# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.api.variant_configuration import get_configuration_result

TEST_CONFIGURATION_DOCTYPE = "Test C2O Configuration"


def create_test_configuration_doctype():
	if frappe.db.exists("DocType", TEST_CONFIGURATION_DOCTYPE):
		return

	frappe.get_doc({
		"doctype": "DocType",
		"name": TEST_CONFIGURATION_DOCTYPE,
		"module": "Config To Order",
		"custom": 1,
		"naming_rule": "Random",
		"fields": [
			{"fieldname": "cpu_item", "fieldtype": "Data", "label": "CPU Item"},
			{"fieldname": "custom_qty", "fieldtype": "Float", "label": "Custom Qty"},
			{"fieldname": "custom_description", "fieldtype": "Data", "label": "Custom Description"},
		],
		"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
	}).insert()


def create_test_item(item_code, **kwargs):
	if frappe.db.exists("Item", item_code):
		return frappe.get_doc("Item", item_code)
	doc = frappe.get_doc(dict(
		doctype="Item",
		item_code=item_code,
		item_name=item_code,
		item_group="All Item Groups",
		stock_uom="Nos",
		is_stock_item=1,
		**kwargs,
	))
	doc.insert()
	return doc


class TestGetConfigurationResult(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			frappe.throw("No Company found - erpnext's before_tests setup did not run")

		create_test_configuration_doctype()

		create_test_item("_Test C2O Laptop")
		create_test_item("_Test C2O CPU Standard")
		create_test_item("_Test C2O CPU Fast")
		create_test_item("_Test C2O RAM")

		if frappe.db.exists("BOM", {"item": "_Test C2O Laptop", "docstatus": 1}):
			cls.bom_name = frappe.db.get_value("BOM", {"item": "_Test C2O Laptop", "docstatus": 1}, "name")
		else:
			bom = frappe.get_doc({
				"doctype": "BOM",
				"item": "_Test C2O Laptop",
				"quantity": 1,
				"company": cls.company,
				"items": [
					{"item_code": "_Test C2O CPU Standard", "qty": 1, "item_from_configuration": "cpu_item"},
					{"item_code": "_Test C2O CPU Fast", "qty": 1, "item_from_configuration": "cpu_item"},
					{
						"item_code": "_Test C2O RAM", "qty": 1,
						"qty_from_configuration": "custom_qty",
						"desc_from_configuration": "custom_description",
					},
				],
			})
			bom.insert()
			bom.submit()
			cls.bom_name = bom.name

	def make_configuration(self, **values):
		doc = frappe.get_doc(dict(doctype=TEST_CONFIGURATION_DOCTYPE, **values))
		doc.insert()
		return doc

	def get_result(self, configuration, args=None):
		full_args = {
			"company": self.company,
			"doctype": "Sales Order",
			"name": "new-sales-order-1",
			"selling_price_list": "Standard Selling",
			"price_list_currency": "USD",
			"transaction_date": frappe.utils.nowdate(),
			"conversion_rate": 1.0,
			"plc_conversion_rate": 1.0,
			"ignore_pricing_rule": 1,
		}
		full_args.update(args or {})
		return get_configuration_result(
			self.bom_name, 0, TEST_CONFIGURATION_DOCTYPE, configuration.name, full_args,
		)

	def test_item_from_configuration_and_overrides_end_to_end(self):
		configuration = self.make_configuration(
			cpu_item="_Test C2O CPU Fast",
			custom_qty=3,
			custom_description="Overridden RAM desc",
		)

		result = self.get_result(configuration)
		items_by_code = {d.item_code: d for d in result.config_items}

		self.assertNotIn("_Test C2O CPU Standard", items_by_code)
		self.assertIn("_Test C2O CPU Fast", items_by_code)
		self.assertEqual(items_by_code["_Test C2O RAM"].qty, 3)
		self.assertEqual(items_by_code["_Test C2O RAM"].description, "Overridden RAM desc")

	def test_args_accepted_as_json_string_like_real_client_call(self):
		# the whitelisted method is called from JS via frm.call(), which frappe serializes
		# to a JSON string on the wire - make sure that path still works after the refactor
		configuration = self.make_configuration(cpu_item="_Test C2O CPU Standard")
		args = {
			"company": self.company, "doctype": "Sales Order", "name": "new-sales-order-2",
			"selling_price_list": "Standard Selling", "price_list_currency": "USD",
			"transaction_date": frappe.utils.nowdate(), "conversion_rate": 1.0,
			"plc_conversion_rate": 1.0, "ignore_pricing_rule": 1,
		}
		result = get_configuration_result(
			self.bom_name, 0, TEST_CONFIGURATION_DOCTYPE, configuration.name, json.dumps(args),
		)
		items_by_code = {d.item_code: d for d in result.config_items}
		self.assertIn("_Test C2O CPU Standard", items_by_code)
		self.assertNotIn("_Test C2O CPU Fast", items_by_code)

	def test_qty_and_description_fall_back_to_bom_values_without_override(self):
		configuration = self.make_configuration(cpu_item="_Test C2O CPU Standard")

		result = self.get_result(configuration)
		items_by_code = {d.item_code: d for d in result.config_items}

		self.assertEqual(items_by_code["_Test C2O RAM"].qty, 1)
		self.assertEqual(items_by_code["_Test C2O RAM"].item_name, "_Test C2O RAM")
