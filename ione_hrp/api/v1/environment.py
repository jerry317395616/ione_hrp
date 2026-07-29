from __future__ import annotations

import frappe

from ione_hrp.services.environment import get_environment_status as get_status
from ione_hrp.services.errors import require_authenticated_user


@frappe.whitelist(methods=["GET"])
def get_environment_status() -> dict[str, object]:
	require_authenticated_user()
	return get_status()
