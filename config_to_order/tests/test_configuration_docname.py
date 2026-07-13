# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.api.variant_configuration import get_configuration_docname

CONFIG_DOCTYPE = "Test C2O Docname Config"


class TestGetConfigurationDocname(FrappeTestCase):
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
				"fields": [{"fieldname": "note", "fieldtype": "Data", "label": "Note"}],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			}).insert()

		if not frappe.db.exists("Item", "_Test C2O Docname Item"):
			frappe.get_doc({
				"doctype": "Item", "item_code": "_Test C2O Docname Item", "item_name": "_Test C2O Docname Item",
				"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
				"is_configurable": 1, "configuration_doctype": CONFIG_DOCTYPE,
			}).insert()

		cls.customer = frappe.db.get_value("Customer", {}, "name")
		if not cls.customer:
			cls.customer = frappe.get_doc({
				"doctype": "Customer", "customer_name": "_Test C2O Docname Customer",
				"customer_group": "Individual", "territory": frappe.db.get_value("Territory", {}, "name"),
			}).insert().name

		cls.configuration = frappe.get_doc({"doctype": CONFIG_DOCTYPE, "note": "for docname test"}).insert()

		cls.sales_order = frappe.get_doc({
			"doctype": "Sales Order", "customer": cls.customer, "company": cls.company,
			"delivery_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
			"items": [{
				"item_code": "_Test C2O Docname Item", "qty": 1, "rate": 10,
				"delivery_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
				"configuration_doctype": CONFIG_DOCTYPE, "configuration_docname": cls.configuration.name,
			}],
		}).insert()

		cls.quotation = frappe.get_doc({
			"doctype": "Quotation", "quotation_to": "Customer", "party_name": cls.customer,
			"company": cls.company,
			"items": [{
				"item_code": "_Test C2O Docname Item", "qty": 1, "rate": 10,
				"configuration_doctype": CONFIG_DOCTYPE, "configuration_docname": cls.configuration.name,
			}],
		}).insert()

	def test_default_source_doctype_is_sales_order_item_unchanged(self):
		rows = get_configuration_docname(
			filters={"configuration_doctype": CONFIG_DOCTYPE}, txt=self.configuration.name)
		names = [r[1] for r in rows]
		self.assertIn(self.sales_order.name, names)

	def test_explicit_sales_order_item_source_doctype(self):
		rows = get_configuration_docname(
			filters={"configuration_doctype": CONFIG_DOCTYPE, "source_doctype": "Sales Order Item"},
			txt=self.configuration.name)
		names = [r[1] for r in rows]
		self.assertIn(self.sales_order.name, names)

	def test_quotation_item_source_doctype(self):
		rows = get_configuration_docname(
			filters={"configuration_doctype": CONFIG_DOCTYPE, "source_doctype": "Quotation Item"},
			txt=self.configuration.name)
		names = [r[1] for r in rows]
		self.assertIn(self.quotation.name, names)
		self.assertNotIn(self.sales_order.name, names)
