from __future__ import annotations

import re

import frappe
from frappe.model.document import Document

_FEATURE_KEY = re.compile(r"^[a-z][a-z0-9_.-]{2,119}$")


class HRPFeatureFlag(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		enabled: DF.Check
		environment: DF.Data
		feature_key: DF.Data
		module_name: DF.Link
	# end: auto-generated types

	def validate(self) -> None:
		self.feature_key = (self.feature_key or "").strip().lower()
		if not _FEATURE_KEY.fullmatch(self.feature_key):
			frappe.throw("Feature Key must use lowercase letters, numbers, dot, underscore or hyphen")
		app_name = frappe.db.get_value("Module Def", self.module_name, "app_name")
		if app_name != "ione_hrp":
			frappe.throw(f"Module {self.module_name} is not owned by ione_hrp")
