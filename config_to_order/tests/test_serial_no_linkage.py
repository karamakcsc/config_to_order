# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.doc_events.serial_and_batch_bundle import on_submit

# Serial No records for a Manufacture Stock Entry are created by erpnext via
# frappe.db.bulk_insert (erpnext/stock/serial_batch_bundle.py) - no Document controller ever
# runs for them. Fully exercising the real chain would mean simulating erpnext's Work Order ->
# Stock Entry -> Serial and Batch Bundle manufacturing flow (warehouses, BOM explosion, GL
# entries, ...), which tests nothing of *this app's* code. Instead this test builds the minimal
# upstream chain (Work Order, Stock Entry) via direct SQL inserts - bypassing their unrelated
# controller validation - and calls our on_submit handler directly with a lightweight mock
# Serial and Batch Bundle doc, to focus on what this app actually owns: the multi-hop lookup
# and the final frappe.db.set_value.


def sql_insert(doctype, values):
	columns = list(values.keys())
	placeholders = ", ".join(["%s"] * len(columns))
	frappe.db.sql(
		"insert into `tab{0}` ({1}) values ({2})".format(doctype, ", ".join("`%s`" % c for c in columns), placeholders),
		list(values.values()),
	)


class TestSerialNoLinkage(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value("Company", {}, "name")
		if not cls.company:
			frappe.throw("No Company found - erpnext's before_tests setup did not run")

		if not frappe.db.exists("Item", "_Test C2O Serial Item"):
			frappe.get_doc({
				"doctype": "Item", "item_code": "_Test C2O Serial Item", "item_name": "_Test C2O Serial Item",
				"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1, "has_serial_no": 1,
			}).insert()

		cls.customer = frappe.db.get_value("Customer", {}, "name")
		if not cls.customer:
			cls.customer = frappe.get_doc({
				"doctype": "Customer", "customer_name": "_Test C2O Serial Customer",
				"customer_group": "Individual", "territory": frappe.db.get_value("Territory", {}, "name"),
			}).insert().name

		if not frappe.db.exists("DocType", "Test C2O Serial Config"):
			frappe.get_doc({
				"doctype": "DocType", "name": "Test C2O Serial Config", "module": "Config To Order",
				"custom": 1, "naming_rule": "Random",
				"fields": [{"fieldname": "note", "fieldtype": "Data", "label": "Note"}],
				"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			}).insert()

	def setUp(self):
		self.configuration = frappe.get_doc({"doctype": "Test C2O Serial Config", "note": "serial linkage test"}).insert()
		self.configuration_result = frappe.get_doc({
			"doctype": "Configuration Result",
			"reference_doctype": "Test C2O Serial Config",
			"reference_docname": self.configuration.name,
		})
		self.configuration_result.set_new_name()
		self.configuration_result.flags.ignore_links = True
		self.configuration_result.insert(ignore_permissions=True)

		self.sales_order = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.customer, "company": self.company,
			"delivery_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
			"items": [{
				"item_code": "_Test C2O Serial Item", "qty": 1, "rate": 10,
				"delivery_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
			}],
		}).insert()
		self.soi_name = self.sales_order.items[0].name
		frappe.db.set_value("Sales Order Item", self.soi_name, "configuration_result", self.configuration_result.name)

		self.work_order_name = frappe.generate_hash(length=10)
		sql_insert("Work Order", {
			"name": self.work_order_name, "sales_order_item": self.soi_name,
			"production_item": "_Test C2O Serial Item", "qty": 1, "company": self.company,
			"docstatus": 1, "owner": "Administrator", "modified_by": "Administrator",
			"creation": frappe.utils.now(), "modified": frappe.utils.now(),
		})

		self.stock_entry_name = frappe.generate_hash(length=10)
		sql_insert("Stock Entry", {
			"name": self.stock_entry_name, "work_order": self.work_order_name,
			"stock_entry_type": "Manufacture", "company": self.company,
			"docstatus": 1, "owner": "Administrator", "modified_by": "Administrator",
			"creation": frappe.utils.now(), "modified": frappe.utils.now(),
		})

		self.serial_no = frappe.generate_hash(length=10)
		frappe.get_doc({
			"doctype": "Serial No", "serial_no": self.serial_no, "item_code": "_Test C2O Serial Item",
		}).insert()

	def make_bundle_doc(self, **overrides):
		bundle = frappe._dict({
			"voucher_type": "Stock Entry",
			"voucher_no": self.stock_entry_name,
			"type_of_transaction": "Inward",
			"entries": [frappe._dict({"serial_no": self.serial_no})],
		})
		bundle.update(overrides)
		return bundle

	def test_links_serial_no_to_configuration_result(self):
		on_submit(self.make_bundle_doc(), "on_submit")
		self.assertEqual(
			frappe.db.get_value("Serial No", self.serial_no, "configuration_result"),
			self.configuration_result.name,
		)

	def test_ignores_non_stock_entry_voucher(self):
		on_submit(self.make_bundle_doc(voucher_type="Delivery Note"), "on_submit")
		self.assertFalse(frappe.db.get_value("Serial No", self.serial_no, "configuration_result"))

	def test_ignores_outward_transactions(self):
		on_submit(self.make_bundle_doc(type_of_transaction="Outward"), "on_submit")
		self.assertFalse(frappe.db.get_value("Serial No", self.serial_no, "configuration_result"))

	def test_noop_when_work_order_has_no_sales_order_item(self):
		work_order_name = frappe.generate_hash(length=10)
		sql_insert("Work Order", {
			"name": work_order_name, "production_item": "_Test C2O Serial Item", "qty": 1,
			"company": self.company, "docstatus": 1, "owner": "Administrator", "modified_by": "Administrator",
			"creation": frappe.utils.now(), "modified": frappe.utils.now(),
		})
		stock_entry_name = frappe.generate_hash(length=10)
		sql_insert("Stock Entry", {
			"name": stock_entry_name, "work_order": work_order_name,
			"stock_entry_type": "Manufacture", "company": self.company,
			"docstatus": 1, "owner": "Administrator", "modified_by": "Administrator",
			"creation": frappe.utils.now(), "modified": frappe.utils.now(),
		})
		on_submit(self.make_bundle_doc(voucher_no=stock_entry_name), "on_submit")
		self.assertFalse(frappe.db.get_value("Serial No", self.serial_no, "configuration_result"))
