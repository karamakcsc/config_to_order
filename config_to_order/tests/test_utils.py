# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.utils import check_selection_condition, get_qty_or_desc


class TestCheckSelectionCondition(FrappeTestCase):
	def test_mandatory_item_with_no_configuration(self):
		# no configuration at all and no condition fields on the row -> always included
		bom_item = frappe._dict({'item_code': 'ITEM-1'})
		self.assertTrue(check_selection_condition(None, bom_item))

	def test_mandatory_item_with_configuration_present(self):
		# a configuration exists, but the row has no item_from_configuration/selection_condition -> mandatory
		configuration = frappe._dict({'color': 'red'})
		bom_item = frappe._dict({'item_code': 'ITEM-1'})
		self.assertTrue(check_selection_condition(configuration, bom_item))

	def test_item_from_configuration_match(self):
		configuration = frappe._dict({'cpu_item': 'ITEM-CPU-FAST'})
		bom_item = frappe._dict({'item_code': 'ITEM-CPU-FAST', 'item_from_configuration': 'cpu_item'})
		self.assertTrue(check_selection_condition(configuration, bom_item))

	def test_item_from_configuration_no_match(self):
		configuration = frappe._dict({'cpu_item': 'ITEM-CPU-FAST'})
		bom_item = frappe._dict({'item_code': 'ITEM-CPU-STANDARD', 'item_from_configuration': 'cpu_item'})
		self.assertFalse(check_selection_condition(configuration, bom_item))

	def test_item_from_configuration_without_a_configuration_is_excluded(self):
		# item_from_configuration is set on the row, but there's no configuration doc to resolve it against
		bom_item = frappe._dict({'item_code': 'ITEM-CPU-FAST', 'item_from_configuration': 'cpu_item'})
		self.assertTrue(check_selection_condition(None, bom_item))

	def test_selection_condition_true_expression(self):
		configuration = frappe._dict({'install_os': 1})
		bom_item = frappe._dict({'item_code': 'ITEM-OS', 'selection_condition': 'doc.install_os == 1'})
		self.assertTrue(check_selection_condition(configuration, bom_item))

	def test_selection_condition_false_expression(self):
		configuration = frappe._dict({'install_os': 0})
		bom_item = frappe._dict({'item_code': 'ITEM-OS', 'selection_condition': 'doc.install_os == 1'})
		self.assertFalse(check_selection_condition(configuration, bom_item))


class TestGetQtyOrDesc(FrappeTestCase):
	def test_falls_back_when_no_configuration(self):
		bom_item = frappe._dict({'qty': 2, 'qty_from_configuration': 'qty_field'})
		self.assertEqual(get_qty_or_desc(None, bom_item, 'qty', 'qty_from_configuration'), 2)

	def test_falls_back_when_bom_item_has_no_override_field_set(self):
		configuration = frappe._dict({'qty_field': 5})
		bom_item = frappe._dict({'qty': 2})
		self.assertEqual(get_qty_or_desc(configuration, bom_item, 'qty', 'qty_from_configuration'), 2)

	def test_falls_back_when_configuration_value_is_empty(self):
		configuration = frappe._dict({'qty_field': None})
		bom_item = frappe._dict({'qty': 2, 'qty_from_configuration': 'qty_field'})
		self.assertEqual(get_qty_or_desc(configuration, bom_item, 'qty', 'qty_from_configuration'), 2)

	def test_uses_configuration_value_when_present(self):
		configuration = frappe._dict({'qty_field': 7})
		bom_item = frappe._dict({'qty': 2, 'qty_from_configuration': 'qty_field'})
		self.assertEqual(get_qty_or_desc(configuration, bom_item, 'qty', 'qty_from_configuration'), 7)

	def test_description_override(self):
		configuration = frappe._dict({'desc_field': 'Custom description'})
		bom_item = frappe._dict({'description': 'Default description', 'desc_from_configuration': 'desc_field'})
		self.assertEqual(
			get_qty_or_desc(configuration, bom_item, 'description', 'desc_from_configuration'),
			'Custom description',
		)
