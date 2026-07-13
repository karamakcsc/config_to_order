# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.api.variant_configuration import get_configuration_result

CONFIG_DOCTYPE = "Test C2O Snapshot Config"


class TestConfigurationSnapshot(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			frappe.throw("No Company found - erpnext's before_tests setup did not run")

		if not frappe.db.exists("DocType", CONFIG_DOCTYPE):
			frappe.get_doc({
				"doctype": "DocType", "name": CONFIG_DOCTYPE, "module": "Config To Order",
				"custom": 1, "naming_rule": "Random",
				"fields": [{"fieldname": "color", "fieldtype": "Data", "label": "Color"}],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			}).insert()

		for item_code in ["_Test C2O Snapshot Item", "_Test C2O Snapshot Raw"]:
			if not frappe.db.exists("Item", item_code):
				frappe.get_doc({
					"doctype": "Item", "item_code": item_code, "item_name": item_code,
					"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
				}).insert()

		if frappe.db.exists("BOM", {"item": "_Test C2O Snapshot Item", "docstatus": 1}):
			cls.bom_name = frappe.db.get_value(
				"BOM", {"item": "_Test C2O Snapshot Item", "docstatus": 1}, "name")
		else:
			bom = frappe.get_doc({
				"doctype": "BOM", "item": "_Test C2O Snapshot Item", "quantity": 1, "company": cls.company,
				"items": [{"item_code": "_Test C2O Snapshot Raw", "qty": 1}],
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

	def test_snapshot_captures_field_values_at_creation(self):
		configuration = frappe.get_doc({"doctype": CONFIG_DOCTYPE, "color": "red"}).insert()

		result = get_configuration_result(self.bom_name, 0, CONFIG_DOCTYPE, configuration.name, self.get_args())

		snapshot = json.loads(result.configuration_snapshot)
		self.assertEqual(snapshot.get("color"), "red")

	def test_snapshot_is_not_retroactively_reinterpreted(self):
		configuration = frappe.get_doc({"doctype": CONFIG_DOCTYPE, "color": "blue"}).insert()

		result = get_configuration_result(self.bom_name, 0, CONFIG_DOCTYPE, configuration.name, self.get_args())
		original_snapshot = json.loads(result.configuration_snapshot)
		self.assertEqual(original_snapshot.get("color"), "blue")

		# edit the source configuration document after the result was created
		configuration.reload()
		configuration.color = "green"
		configuration.save()

		# the already-created result's snapshot must still reflect what was true when it was made
		unchanged_snapshot = json.loads(result.configuration_snapshot)
		self.assertEqual(unchanged_snapshot.get("color"), "blue")
