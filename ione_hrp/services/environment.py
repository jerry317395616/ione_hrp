from __future__ import annotations

from typing import Any

import frappe

from ione_hrp.common.environment_profiles import (
	EnvironmentProfileError,
	load_environment_registry,
)


def _normalized_config_value(value: Any, expected: object) -> object:
	if isinstance(expected, bool):
		if value in (0, 1, False, True):
			return bool(value)
		if isinstance(value, str) and value in {"0", "1"}:
			return value == "1"
	if isinstance(expected, int) and isinstance(value, str) and value.isdigit():
		return int(value)
	return value


def get_environment_status() -> dict[str, object]:
	environment_name = str(frappe.conf.get("ione_hrp_environment") or "").strip()
	if not environment_name:
		return {
			"managed": False,
			"name": "unmanaged",
			"schema_version": None,
		}

	registry = load_environment_registry()
	try:
		profile = registry.get(environment_name)
	except EnvironmentProfileError as exc:
		frappe.throw(str(exc), frappe.ValidationError)

	expected_config = profile.expected_site_config(registry.schema_version)
	drift = [
		key
		for key, expected in expected_config.items()
		if _normalized_config_value(frappe.conf.get(key), expected) != expected
	]
	if drift:
		frappe.throw(
			f"Environment configuration drift: {', '.join(sorted(drift))}",
			frappe.ValidationError,
		)
	return profile.as_public_dict(registry.schema_version)


def assert_external_integrations_allowed() -> None:
	status = get_environment_status()
	if not status.get("managed") or not status.get("external_integrations_enabled"):
		frappe.throw(
			"External integrations are disabled for this environment",
			frappe.PermissionError,
		)
