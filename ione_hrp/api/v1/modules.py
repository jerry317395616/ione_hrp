from __future__ import annotations

import frappe
from frappe.utils import cint

from ione_hrp.setup.modules import declared_modules


@frappe.whitelist(methods=["GET"])
def list_modules() -> list[dict[str, object]]:
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)

    settings = {
        row.module_name: row
        for row in frappe.get_all(
            "HRP Module Setting",
            fields=["module_name", "module_key", "domain_group", "label_cn", "enabled", "sequence", "description"],
        )
    }
    result: list[dict[str, object]] = []
    for order, module_name in enumerate(declared_modules(), start=10):
        row = settings.get(module_name)
        result.append(
            {
                "module": module_name,
                "module_key": row.module_key if row else frappe.scrub(module_name),
                "domain_group": row.domain_group if row else "Other",
                "label_cn": row.label_cn if row else module_name,
                "enabled": bool(row.enabled) if row else True,
                "sequence": row.sequence if row else order,
                "description": row.description if row else "",
            }
        )
    return sorted(result, key=lambda item: (int(item["sequence"]), str(item["module"])))


@frappe.whitelist(methods=["POST"])
def set_module_enabled(module_name: str, enabled: int | str | bool) -> dict[str, object]:
    frappe.only_for("System Manager")
    if module_name not in declared_modules():
        frappe.throw(f"Module is not declared by ione_hrp: {module_name}")
    doc = frappe.get_doc("HRP Module Setting", module_name)
    doc.enabled = cint(enabled)
    doc.save()
    return {"module": module_name, "enabled": bool(doc.enabled)}
