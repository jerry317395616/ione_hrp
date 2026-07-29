from __future__ import annotations

from unittest.mock import patch

from frappe.tests import IntegrationTestCase

from ione_hrp.common.error_catalog import IoneApplicationError
from ione_hrp.setup.demo import (
	SYNTHETIC_COMPANY_NAME,
	setup_synthetic_demo,
)


class TestSyntheticDemoSetup(IntegrationTestCase):
	def test_rejects_non_demo_environment_before_writes(self) -> None:
		with (
			patch(
				"ione_hrp.setup.demo.get_environment_status",
				return_value={"name": "test", "synthetic_data_only": True},
			),
			patch("ione_hrp.setup.demo.setup_complete") as setup,
			self.assertRaises(IoneApplicationError) as raised,
		):
			setup_synthetic_demo()
		self.assertEqual(raised.exception.code, "IONE-CORE-0008")
		setup.assert_not_called()

	def test_existing_synthetic_company_is_idempotent(self) -> None:
		with (
			patch(
				"ione_hrp.setup.demo.get_environment_status",
				return_value={"name": "demo", "synthetic_data_only": True},
			),
			patch(
				"ione_hrp.setup.demo.frappe.get_all",
				return_value=[SYNTHETIC_COMPANY_NAME],
			),
			patch("ione_hrp.setup.demo.setup_complete") as setup,
		):
			result = setup_synthetic_demo()
		self.assertFalse(result["changed"])
		setup.assert_not_called()

	def test_existing_non_demo_company_is_rejected(self) -> None:
		with (
			patch(
				"ione_hrp.setup.demo.get_environment_status",
				return_value={"name": "demo", "synthetic_data_only": True},
			),
			patch(
				"ione_hrp.setup.demo.frappe.get_all",
				return_value=["Real Hospital"],
			),
			patch("ione_hrp.setup.demo.setup_complete") as setup,
			self.assertRaises(IoneApplicationError) as raised,
		):
			setup_synthetic_demo()
		self.assertEqual(raised.exception.code, "IONE-CORE-0005")
		setup.assert_not_called()

	def test_new_demo_uses_standard_erpnext_setup_controller(self) -> None:
		with (
			patch(
				"ione_hrp.setup.demo.get_environment_status",
				return_value={"name": "demo", "synthetic_data_only": True},
			),
			patch("ione_hrp.setup.demo.frappe.get_all", return_value=[]),
			patch("ione_hrp.setup.demo.setup_complete") as setup,
		):
			result = setup_synthetic_demo()
		self.assertTrue(result["changed"])
		setup.assert_called_once()
		self.assertEqual(setup.call_args.args[0]["company_name"], SYNTHETIC_COMPANY_NAME)
