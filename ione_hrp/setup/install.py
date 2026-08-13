from __future__ import annotations

import frappe

from ione_hrp.common.constants import CORE_ROLES
from ione_hrp.setup.access_scope import ensure_access_scope_governance
from ione_hrp.setup.approval_matrix import ensure_approval_matrix_governance
from ione_hrp.setup.master_data import ensure_master_data_governance
from ione_hrp.setup.modules import sync_module_defs, sync_module_settings
from ione_hrp.setup.numbering import ensure_numbering_governance
from ione_hrp.setup.organization import ensure_organization_hierarchy
from ione_hrp.setup.settings import ensure_system_settings
from ione_hrp.setup.versions import validate_runtime_versions
from ione_hrp.setup.workspaces import sync_owned_workspaces


def _ensure_roles() -> None:
	for role_name in CORE_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
				"is_custom": 0,
			}
		).insert(ignore_permissions=True)


def after_install() -> None:
	validate_runtime_versions()
	sync_module_defs()
	_ensure_roles()
	sync_module_settings()
	ensure_organization_hierarchy()
	ensure_master_data_governance()
	ensure_numbering_governance()
	ensure_access_scope_governance()
	ensure_approval_matrix_governance()
	ensure_system_settings()
	sync_owned_workspaces()


def after_migrate() -> None:
	validate_runtime_versions()
	sync_module_defs()
	_ensure_roles()
	sync_module_settings()
	ensure_organization_hierarchy()
	ensure_master_data_governance()
	ensure_numbering_governance()
	ensure_access_scope_governance()
	ensure_approval_matrix_governance()
	ensure_system_settings()
	sync_owned_workspaces()


def before_uninstall() -> None:
	# Frappe displays a destructive uninstall confirmation and removes Module Def-owned records.
	# This hook exists so future releases can add domain-specific archival checks.
	return None
