from __future__ import annotations

from importlib import import_module

import frappe
from packaging.version import Version

from ione_hrp.common.constants import SUPPORTED_MAJOR


def get_runtime_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for app in ("frappe", "erpnext", "hrms", "ione_hrp"):
        module = import_module(app)
        versions[app] = str(getattr(module, "__version__", "unknown"))
    return versions


def validate_runtime_versions() -> dict[str, str]:
    versions = get_runtime_versions()
    incompatible: list[str] = []
    for app in ("frappe", "erpnext", "hrms"):
        raw = versions[app]
        try:
            major = Version(raw).major
        except Exception:
            incompatible.append(f"{app}={raw} (cannot parse)")
            continue
        if major != SUPPORTED_MAJOR:
            incompatible.append(f"{app}={raw}")
    if incompatible:
        frappe.throw(
            "ione_hrp requires Frappe ecosystem major "
            f"{SUPPORTED_MAJOR}; incompatible: {', '.join(incompatible)}"
        )
    return versions
