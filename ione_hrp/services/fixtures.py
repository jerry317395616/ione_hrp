from __future__ import annotations

from pathlib import Path

import frappe

from ione_hrp.common.constants import APP_NAME
from ione_hrp.common.fixture_policy import (
	FixturePolicyError,
	inspect_fixture_repository,
	load_fixture_policy,
)
from ione_hrp.services.environment import get_environment_status


def _fixture_directory() -> Path:
	return Path(frappe.get_app_path(APP_NAME, "fixtures"))


def _require_system_manager() -> None:
	frappe.only_for("System Manager")


def get_fixture_governance_status() -> dict[str, object]:
	_require_system_manager()
	try:
		policy = load_fixture_policy()
		repository = inspect_fixture_repository(policy, _fixture_directory())
	except FixturePolicyError as exc:
		frappe.throw(str(exc), frappe.ValidationError)
	return {
		"policy": policy.as_public_dict(),
		"repository": repository.as_dict(),
		"export": {
			"http_write_enabled": False,
			"development_environment_required": True,
			"explicit_confirmation_required": True,
		},
	}


def assert_fixture_export_allowed() -> dict[str, object]:
	"""Fail closed before the OS-level fixture exporter writes app source."""
	status = get_environment_status()
	if (
		not status.get("managed")
		or status.get("name") != "development"
		or not frappe.conf.get("developer_mode")
		or not frappe.conf.get("allow_tests")
		or status.get("external_integrations_enabled")
	):
		frappe.throw(
			"Fixture export is allowed only on the managed development environment",
			frappe.PermissionError,
		)
	try:
		policy = load_fixture_policy()
		repository = inspect_fixture_repository(policy, _fixture_directory())
	except FixturePolicyError as exc:
		frappe.throw(str(exc), frappe.ValidationError)
	return {
		"status": "ok",
		"environment": "development",
		"schema_version": policy.schema_version,
		"repository_sha256": repository.sha256,
	}
