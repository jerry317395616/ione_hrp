from __future__ import annotations

import frappe

from ione_hrp.setup.versions import get_runtime_versions, get_version_status


@frappe.whitelist(methods=["GET"])
def get_health() -> dict[str, object]:
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)
    return {
        "status": "ok",
        "site": frappe.local.site,
        "user": frappe.session.user,
        "versions": get_runtime_versions(),
        "installed_apps": frappe.get_installed_apps(),
    }


@frappe.whitelist(methods=["GET"])
def get_upstream_version_status() -> dict[str, object]:
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)
    return get_version_status()
