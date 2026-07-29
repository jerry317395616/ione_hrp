from __future__ import annotations

import frappe

from ione_hrp.services.fixtures import get_fixture_governance_status as get_status


@frappe.whitelist(methods=["GET"])
def get_fixture_governance_status() -> dict[str, object]:
	if frappe.session.user == "Guest":
		frappe.throw("Authentication required", frappe.AuthenticationError)
	return get_status()
