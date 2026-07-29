from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from ione_hrp.api.v1.health import get_upstream_version_status
from ione_hrp.setup.versions import get_version_status


class TestUpstreamVersionLock(IntegrationTestCase):
    def test_runtime_matches_resolved_lock(self) -> None:
        status = get_version_status()
        self.assertEqual(status["status"], "match", status["issues"])

    def test_version_status_rejects_guest(self) -> None:
        original_user = frappe.session.user
        try:
            frappe.set_user("Guest")
            with self.assertRaises(frappe.AuthenticationError):
                get_upstream_version_status()
        finally:
            frappe.set_user(original_user)
