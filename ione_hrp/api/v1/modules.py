from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict, cast

import frappe
from frappe.utils import cint

from ione_hrp.services.audit_context import emit_audit_event, service_audit_scope
from ione_hrp.services.errors import (
	raise_ione_error,
	require_authenticated_user,
	require_roles,
)
from ione_hrp.services.module_registry import load_module_registry

if TYPE_CHECKING:
	from ione_hrp.hrp_foundation.doctype.hrp_module_setting.hrp_module_setting import (
		HRPModuleSetting,
	)

MODULE_ADMIN_ROLES = frozenset({"System Manager", "HRP System Manager"})


class ModuleView(TypedDict):
	module: str
	module_key: str
	domain_group: str
	label_cn: str
	enabled: bool
	sequence: int
	description: str


def _require_module_admin() -> None:
	require_roles(MODULE_ADMIN_ROLES)


@frappe.whitelist(methods=["GET"])
def list_modules() -> list[ModuleView]:
	with service_audit_scope():
		require_authenticated_user()
		registry = load_module_registry()
		settings = {}
		if frappe.db.exists("DocType", "HRP Module Setting"):
			settings = {
				row.module_name: row
				for row in frappe.get_all(
					"HRP Module Setting",
					fields=[
						"module_name",
						"module_key",
						"domain_group",
						"label_cn",
						"enabled",
						"sequence",
						"description",
					],
				)
			}

		result: list[ModuleView] = []
		for module in registry.modules:
			row = settings.get(module.module)
			result.append(
				{
					"module": module.module,
					"module_key": row.module_key if row else module.package,
					"domain_group": row.domain_group if row else module.domain_group,
					"label_cn": row.label_cn if row else module.label_cn,
					"enabled": bool(row.enabled) if row else module.enabled_by_default,
					"sequence": row.sequence if row else module.sequence,
					"description": row.description if row else module.description,
				}
			)
		return sorted(result, key=lambda item: (item["sequence"], item["module"]))


@frappe.whitelist(methods=["POST"])
def set_module_enabled(
	module_name: str,
	enabled: int | str | bool,
	correlation_id: str | None = None,
) -> dict[str, object]:
	"""Idempotently change a published module setting and leave an audit trail."""
	with service_audit_scope(correlation_id) as context:
		_require_module_admin()
		modules = {row.module: row for row in load_module_registry().modules}
		if module_name not in modules:
			raise_ione_error("RESOURCE_NOT_FOUND")

		doc = cast("HRPModuleSetting", frappe.get_doc("HRP Module Setting", module_name))
		desired = int(bool(cint(enabled)))
		current = int(bool(doc.enabled))
		if desired == current:
			emit_audit_event(
				"module_enabled_unchanged",
				logger_name="ione_hrp.module_registry",
				module=module_name,
				enabled=bool(current),
			)
			return {
				"module": module_name,
				"enabled": bool(current),
				"changed": False,
				"correlation_id": context.correlation_id,
			}

		doc.enabled = desired
		doc.save()
		audit_message = (
			f"Module enabled changed from {bool(current)} to {bool(desired)}; "
			f"correlation_id={context.correlation_id}; request_id={context.request_id}"
		)
		doc.add_comment("Info", audit_message)
		emit_audit_event(
			"module_enabled_changed",
			logger_name="ione_hrp.module_registry",
			module=module_name,
			before=bool(current),
			after=bool(desired),
		)
		return {
			"module": module_name,
			"enabled": bool(desired),
			"changed": True,
			"correlation_id": context.correlation_id,
		}
