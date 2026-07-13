# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe


def on_submit(doc, method):
	"""Link newly manufactured Serial Nos back to the Configuration Result that drove their build.

	Serial No records for a Manufacture Stock Entry are created via frappe.db.bulk_insert
	(erpnext/stock/serial_batch_bundle.py) - no Serial No doc_events ever fire for them, so this
	hooks Serial and Batch Bundle's on_submit instead, which *does* go through a normal
	doc.save() and therefore fires doc_events normally.
	"""
	if doc.voucher_type != 'Stock Entry' or not doc.voucher_no:
		return
	if doc.get('type_of_transaction') and doc.type_of_transaction != 'Inward':
		return

	serial_nos = [d.serial_no for d in doc.entries if d.serial_no]
	if not serial_nos:
		return

	work_order = frappe.db.get_value('Stock Entry', doc.voucher_no, 'work_order')
	if not work_order:
		return

	sales_order_item = frappe.db.get_value('Work Order', work_order, 'sales_order_item')
	if not sales_order_item:
		return

	configuration_result = frappe.db.get_value('Sales Order Item', sales_order_item, 'configuration_result')
	if not configuration_result:
		return

	for serial_no in serial_nos:
		# frappe.db.set_value, not doc.save(), so this doesn't re-trigger Serial No validation
		frappe.db.set_value('Serial No', serial_no, 'configuration_result', configuration_result)
