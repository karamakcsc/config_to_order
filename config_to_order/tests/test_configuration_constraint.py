# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from config_to_order.utils import (
	evaluate_constraint,
	get_active_constraints,
	validate_configuration_constraints,
)

TEST_CONSTRAINT_CONFIGURATION_DOCTYPE = "Test C2O Constraint Config"


def create_test_constraint_configuration_doctype():
	if frappe.db.exists("DocType", TEST_CONSTRAINT_CONFIGURATION_DOCTYPE):
		return

	frappe.get_doc({
		"doctype": "DocType",
		"name": TEST_CONSTRAINT_CONFIGURATION_DOCTYPE,
		"module": "Config To Order",
		"custom": 1,
		"naming_rule": "Random",
		"fields": [
			{"fieldname": "motor_type", "fieldtype": "Select", "label": "Motor Type",
				"options": "3HP\n5HP\n7.5HP"},
			{"fieldname": "control_panel_voltage", "fieldtype": "Data", "label": "Control Panel Voltage"},
			{"fieldname": "panel_length", "fieldtype": "Float", "label": "Panel Length"},
			{"fieldname": "install_os", "fieldtype": "Check", "label": "Install OS"},
		],
		"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
	}).insert()


def make_constraint(**values):
	defaults = {"configuration_doctype": TEST_CONSTRAINT_CONFIGURATION_DOCTYPE, "constraint_type": "Requires"}
	defaults.update(values)
	return frappe.get_doc(dict(doctype="Configuration Constraint", **defaults)).insert()


class TestEvaluateConstraint(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_constraint_configuration_doctype()

	def test_requires_satisfied(self):
		configuration = frappe._dict({"motor_type": "5HP", "control_panel_voltage": "380V"})
		constraint = frappe._dict({
			"constraint_type": "Requires",
			"if_field": "motor_type", "if_operator": "=", "if_value": "5HP",
			"then_field": "control_panel_voltage", "then_operator": "in", "then_value": "380V,415V",
		})
		self.assertTrue(evaluate_constraint(configuration, constraint))

	def test_requires_violated(self):
		configuration = frappe._dict({"motor_type": "5HP", "control_panel_voltage": "220V"})
		constraint = frappe._dict({
			"constraint_type": "Requires",
			"if_field": "motor_type", "if_operator": "=", "if_value": "5HP",
			"then_field": "control_panel_voltage", "then_operator": "in", "then_value": "380V,415V",
		})
		self.assertFalse(evaluate_constraint(configuration, constraint))

	def test_requires_if_side_not_matching_is_always_satisfied(self):
		# motor_type is 3HP, so the "if" side never triggers - the then side is irrelevant
		configuration = frappe._dict({"motor_type": "3HP", "control_panel_voltage": "220V"})
		constraint = frappe._dict({
			"constraint_type": "Requires",
			"if_field": "motor_type", "if_operator": "=", "if_value": "5HP",
			"then_field": "control_panel_voltage", "then_operator": "in", "then_value": "380V,415V",
		})
		self.assertTrue(evaluate_constraint(configuration, constraint))

	def test_excludes_satisfied(self):
		configuration = frappe._dict({"motor_type": "5HP", "control_panel_voltage": "380V"})
		constraint = frappe._dict({
			"constraint_type": "Excludes",
			"if_field": "motor_type", "if_operator": "=", "if_value": "5HP",
			"then_field": "control_panel_voltage", "then_operator": "=", "then_value": "220V",
		})
		self.assertTrue(evaluate_constraint(configuration, constraint))

	def test_excludes_violated(self):
		configuration = frappe._dict({"motor_type": "5HP", "control_panel_voltage": "220V"})
		constraint = frappe._dict({
			"constraint_type": "Excludes",
			"if_field": "motor_type", "if_operator": "=", "if_value": "5HP",
			"then_field": "control_panel_voltage", "then_operator": "=", "then_value": "220V",
		})
		self.assertFalse(evaluate_constraint(configuration, constraint))

	def test_range_satisfied(self):
		configuration = frappe._dict({"panel_length": 100})
		constraint = frappe._dict({"constraint_type": "Range", "range_field": "panel_length", "min_value": 50, "max_value": 200})
		self.assertTrue(evaluate_constraint(configuration, constraint))

	def test_range_violated_below_min(self):
		configuration = frappe._dict({"panel_length": 10})
		constraint = frappe._dict({"constraint_type": "Range", "range_field": "panel_length", "min_value": 50, "max_value": 200})
		self.assertFalse(evaluate_constraint(configuration, constraint))

	def test_range_violated_above_max(self):
		configuration = frappe._dict({"panel_length": 300})
		constraint = frappe._dict({"constraint_type": "Range", "range_field": "panel_length", "min_value": 50, "max_value": 200})
		self.assertFalse(evaluate_constraint(configuration, constraint))

	def test_range_skips_when_value_missing(self):
		configuration = frappe._dict({"panel_length": None})
		constraint = frappe._dict({"constraint_type": "Range", "range_field": "panel_length", "min_value": 50, "max_value": 200})
		self.assertTrue(evaluate_constraint(configuration, constraint))

	def test_expression_satisfied(self):
		configuration = frappe._dict({"install_os": 1})
		constraint = frappe._dict({"constraint_type": "Expression", "expression": "doc.install_os == 1"})
		self.assertTrue(evaluate_constraint(configuration, constraint))

	def test_expression_violated(self):
		configuration = frappe._dict({"install_os": 0})
		constraint = frappe._dict({"constraint_type": "Expression", "expression": "doc.install_os == 1"})
		self.assertFalse(evaluate_constraint(configuration, constraint))


class TestValidateConfigurationConstraints(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_constraint_configuration_doctype()
		cls.constraint = make_constraint(
			constraint_type="Requires",
			if_field="motor_type", if_operator="=", if_value="5HP",
			then_field="control_panel_voltage", then_operator="in", then_value="380V,415V",
			message="5HP motors require a 380V or 415V control panel.",
		)

	def test_raises_with_constraint_message_on_violation(self):
		configuration = frappe._dict({
			"doctype": TEST_CONSTRAINT_CONFIGURATION_DOCTYPE,
			"motor_type": "5HP", "control_panel_voltage": "220V",
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			validate_configuration_constraints(configuration)
		self.assertIn("5HP motors require a 380V or 415V control panel.", str(ctx.exception))

	def test_silent_when_satisfied(self):
		configuration = frappe._dict({
			"doctype": TEST_CONSTRAINT_CONFIGURATION_DOCTYPE,
			"motor_type": "5HP", "control_panel_voltage": "380V",
		})
		validate_configuration_constraints(configuration)  # should not raise

	def test_get_active_constraints_ignores_inactive(self):
		inactive = make_constraint(
			constraint_type="Range", range_field="panel_length", min_value=1, max_value=2, is_active=0,
		)
		try:
			names = [c.name for c in get_active_constraints(TEST_CONSTRAINT_CONFIGURATION_DOCTYPE)]
			self.assertIn(self.constraint.name, names)
			self.assertNotIn(inactive.name, names)
		finally:
			frappe.delete_doc("Configuration Constraint", inactive.name, force=1)


class TestConfigurationConstraintController(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_constraint_configuration_doctype()

	def test_rejects_nonexistent_if_field(self):
		with self.assertRaises(frappe.ValidationError):
			make_constraint(
				constraint_type="Requires",
				if_field="does_not_exist", if_operator="=", if_value="5HP",
				then_field="control_panel_voltage", then_operator="=", then_value="380V",
			)

	def test_rejects_nonexistent_then_field(self):
		with self.assertRaises(frappe.ValidationError):
			make_constraint(
				constraint_type="Requires",
				if_field="motor_type", if_operator="=", if_value="5HP",
				then_field="does_not_exist", then_operator="=", then_value="380V",
			)

	def test_rejects_nonexistent_range_field(self):
		with self.assertRaises(frappe.ValidationError):
			make_constraint(constraint_type="Range", range_field="does_not_exist", min_value=1, max_value=2)

	def test_rejects_expression_that_fails_test_evaluation(self):
		with self.assertRaises(frappe.ValidationError):
			make_constraint(constraint_type="Expression", expression="doc.totally_bogus_field ===")

	def test_accepts_valid_expression(self):
		constraint = make_constraint(constraint_type="Expression", expression="doc.install_os == 1")
		self.assertTrue(constraint.name)

	def test_requires_missing_structured_fields_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_constraint(constraint_type="Requires")

	def test_range_missing_bounds_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_constraint(constraint_type="Range", range_field="panel_length")


class TestWildcardHookIsNoOpForUnrelatedDoctypes(FrappeTestCase):
	def test_note_save_does_not_trigger_constraint_evaluation(self):
		self.assertFalse(frappe.db.exists("Configuration Constraint", {"configuration_doctype": "Note", "is_active": 1}))

		with patch("config_to_order.doc_events.configuration.validate_configuration_constraints") as mocked:
			note = frappe.get_doc({"doctype": "Note", "title": "C2O wildcard hook smoke test"}).insert()
			mocked.assert_not_called()

		frappe.delete_doc("Note", note.name, force=1)

	def test_todo_save_is_unaffected(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "C2O wildcard hook smoke test"}).insert()
		self.assertTrue(todo.name)
		frappe.delete_doc("ToDo", todo.name, force=1)
