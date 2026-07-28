from __future__ import annotations

from pathlib import Path

import frappe

from ione_hrp.common.constants import APP_NAME


def declared_modules() -> list[str]:
    return frappe.get_module_list(APP_NAME)


def sync_module_defs() -> dict[str, list[str]]:
    """Create missing Module Def rows declared in modules.txt.

    Existing rows are never deleted automatically because deleting a Module Def can cascade
    to standard records. A conflicting app owner is treated as a hard error.
    """
    created: list[str] = []
    existing: list[str] = []
    conflicts: list[str] = []

    for module_name in declared_modules():
        owner = frappe.db.get_value("Module Def", module_name, "app_name")
        if owner is None:
            frappe.get_doc(
                {
                    "doctype": "Module Def",
                    "module_name": module_name,
                    "app_name": APP_NAME,
                    "custom": 0,
                }
            ).insert(ignore_permissions=True)
            created.append(module_name)
        elif owner != APP_NAME:
            conflicts.append(f"{module_name} -> {owner}")
        else:
            existing.append(module_name)

    if conflicts:
        frappe.throw("Module Def ownership conflict: " + "; ".join(conflicts))

    return {"created": created, "existing": existing, "conflicts": conflicts}


def sync_module_settings() -> int:
    if not frappe.db.exists("DocType", "HRP Module Setting"):
        return 0

    registry_path = Path(frappe.get_app_source_path(APP_NAME, "architecture", "module_registry.yaml"))
    # Packaged deployments may not include repository-level architecture files. In that case,
    # modules.txt remains the authoritative source and defaults are inferred.
    registry: dict[str, dict] = {}
    if registry_path.exists():
        try:
            import yaml
            payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
            registry = {row["module"]: row for row in payload.get("modules", [])}
        except Exception:
            frappe.log_error(frappe.get_traceback(), "HRP module registry read failed")

    inserted = 0
    for sequence, module_name in enumerate(declared_modules(), start=10):
        if frappe.db.exists("HRP Module Setting", module_name):
            continue
        meta = registry.get(module_name, {})
        frappe.get_doc(
            {
                "doctype": "HRP Module Setting",
                "module_name": module_name,
                "module_key": meta.get("package") or frappe.scrub(module_name),
                "domain_group": meta.get("domain_group") or "Other",
                "label_cn": meta.get("label_cn") or module_name,
                "enabled": 1,
                "sequence": meta.get("sequence") or sequence,
                "description": meta.get("description") or "",
            }
        ).insert(ignore_permissions=True)
        inserted += 1
    return inserted
