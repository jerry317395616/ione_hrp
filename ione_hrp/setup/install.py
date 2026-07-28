from __future__ import annotations

import frappe

from ione_hrp.common.constants import CORE_ROLES
from ione_hrp.setup.modules import sync_module_defs, sync_module_settings
from ione_hrp.setup.versions import validate_runtime_versions


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


def after_migrate() -> None:
    validate_runtime_versions()
    sync_module_defs()
    _ensure_roles()
    sync_module_settings()


def before_uninstall() -> None:
    # Frappe displays a destructive uninstall confirmation and removes Module Def-owned records.
    # This hook exists so future releases can add domain-specific archival checks.
    return None
