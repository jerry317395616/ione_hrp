from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from ione_hrp.api.v1.modules import list_modules, set_module_enabled
from ione_hrp.services.module_registry import load_module_registry
from ione_hrp.setup.modules import sync_module_defs, sync_module_settings


class TestModuleRegistry(IntegrationTestCase):
	def test_registry_and_site_are_consistent(self) -> None:
		registry = load_module_registry()
		self.assertEqual(len(registry.modules), 36)
		self.assertEqual(len(list_modules()), 36)
		self.assertSetEqual(
			set(
				frappe.get_all(
					"Module Def",
					filters={"app_name": "ione_hrp"},
					pluck="module_name",
				)
			),
			set(
				frappe.get_all(
					"HRP Module Setting",
					order_by="sequence asc",
					pluck="module_name",
				)
			),
		)

	def test_sync_is_idempotent_and_repairs_metadata_without_changing_enabled(self) -> None:
		module = load_module_registry().modules[0]
		original_enabled = frappe.db.get_value(
			"HRP Module Setting",
			module.module,
			"enabled",
		)
		frappe.db.set_value(
			"HRP Module Setting",
			module.module,
			"label_cn",
			"drifted label",
			update_modified=False,
		)

		first = sync_module_settings()
		second = sync_module_settings()

		self.assertIn(module.module, first["updated"])
		self.assertEqual(second["created"], [])
		self.assertEqual(second["updated"], [])
		self.assertEqual(len(second["unchanged"]), 36)
		self.assertEqual(
			frappe.db.get_value("HRP Module Setting", module.module, "label_cn"),
			module.label_cn,
		)
		self.assertEqual(
			frappe.db.get_value("HRP Module Setting", module.module, "enabled"),
			original_enabled,
		)

	def test_module_def_conflict_is_preflighted_before_any_write(self) -> None:
		with (
			patch.object(frappe.db, "get_value", return_value="another_app"),
			patch.object(frappe, "get_doc") as get_doc,
			self.assertRaises(frappe.ValidationError),
		):
			sync_module_defs()
		get_doc.assert_not_called()

	def test_module_list_rejects_guest(self) -> None:
		original_user = frappe.session.user or "Administrator"
		try:
			frappe.set_user("Guest")
			with self.assertRaises(frappe.AuthenticationError):
				list_modules()
		finally:
			frappe.set_user(original_user)

	def test_module_write_requires_module_admin_role(self) -> None:
		module = load_module_registry().modules[0]
		with (
			patch("ione_hrp.api.v1.modules.frappe.get_roles", return_value=["HRP User"]),
			self.assertRaises(frappe.PermissionError),
		):
			set_module_enabled(module.module, True, "COD-003-permission-test")

	def test_module_write_is_idempotent_and_audited(self) -> None:
		module = load_module_registry().modules[0]
		original_enabled = bool(frappe.db.get_value("HRP Module Setting", module.module, "enabled"))
		unchanged = set_module_enabled(
			module.module,
			original_enabled,
			"COD-003-idempotent-test",
		)
		self.assertFalse(unchanged["changed"])

		changed = set_module_enabled(
			module.module,
			not original_enabled,
			"COD-003-audit-test",
		)
		self.assertTrue(changed["changed"])
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "HRP Module Setting",
					"reference_name": module.module,
					"content": ["like", "%COD-003-audit-test%"],
				},
			)
		)
		set_module_enabled(
			module.module,
			original_enabled,
			"COD-003-audit-restore",
		)

	def test_module_write_rejects_invalid_input_before_mutation(self) -> None:
		module = load_module_registry().modules[0]
		original_enabled = frappe.db.get_value(
			"HRP Module Setting",
			module.module,
			"enabled",
		)
		with self.assertRaises(frappe.ValidationError):
			set_module_enabled(module.module, not bool(original_enabled), "../invalid")
		self.assertEqual(
			frappe.db.get_value("HRP Module Setting", module.module, "enabled"),
			original_enabled,
		)

		with self.assertRaises(frappe.ValidationError):
			set_module_enabled("HRP Not Declared", True, "COD-003-invalid-module")
