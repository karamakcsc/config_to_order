# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.api.variant_configuration import get_configuration_result

CONFIG_DOCTYPE = "Test C2O Price Formula Config"


class TestPriceFormula(FrappeTestCase):
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
				"fields": [
					{"fieldname": "length", "fieldtype": "Float", "label": "Length"},
					{"fieldname": "width", "fieldtype": "Float", "label": "Width"},
				],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			}).insert()

		for item_code in ["_Test C2O Custom Glass Panel", "_Test C2O Fixed Frame"]:
			if not frappe.db.exists("Item", item_code):
				frappe.get_doc({
					"doctype": "Item", "item_code": item_code, "item_name": item_code,
					"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
				}).insert()

		if frappe.db.exists("BOM", {"item": "_Test C2O Custom Glass Panel", "docstatus": 1}):
			cls.bom_name = frappe.db.get_value(
				"BOM", {"item": "_Test C2O Custom Glass Panel", "docstatus": 1}, "name")
		else:
			bom = frappe.get_doc({
				"doctype": "BOM", "item": "_Test C2O Custom Glass Panel", "quantity": 1, "company": cls.company,
				"items": [
					{"item_code": "_Test C2O Fixed Frame", "qty": 1,
						"price_formula": "doc.length * doc.width * 10"},
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

	def test_formula_price_used_instead_of_item_price(self):
		configuration = frappe.get_doc({"doctype": CONFIG_DOCTYPE, "length": 3, "width": 4}).insert()

		result = get_configuration_result(self.bom_name, 0, CONFIG_DOCTYPE, configuration.name, self.get_args())

		frame_row = next(d for d in result.config_items if d.item_code == "_Test C2O Fixed Frame")
		self.assertEqual(frame_row.rate, 3 * 4 * 10)
		self.assertEqual(frame_row.amount, frame_row.rate * frame_row.qty)

	def test_formula_scales_with_dimensions(self):
		configuration = frappe.get_doc({"doctype": CONFIG_DOCTYPE, "length": 2, "width": 5}).insert()

		result = get_configuration_result(self.bom_name, 0, CONFIG_DOCTYPE, configuration.name, self.get_args())

		frame_row = next(d for d in result.config_items if d.item_code == "_Test C2O Fixed Frame")
		self.assertEqual(frame_row.rate, 2 * 5 * 10)
