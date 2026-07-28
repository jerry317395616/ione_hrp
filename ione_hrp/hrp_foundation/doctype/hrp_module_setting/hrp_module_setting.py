from __future__ import annotations

import frappe
from frappe.model.document import Document


class HRPModuleSetting(Document):
    def validate(self) -> None:
        app_name = frappe.db.get_value("Module Def", self.module_name, "app_name")
        if app_name != "ione_hrp":
            frappe.throw(f"Module {self.module_name} is not owned by ione_hrp")
