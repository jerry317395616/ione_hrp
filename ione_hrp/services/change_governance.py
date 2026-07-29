from __future__ import annotations

import re
from pathlib import Path

import frappe

from ione_hrp.common.change_governance import (
	ChangeGovernanceError,
	inspect_change_governance,
)
from ione_hrp.common.constants import APP_NAME

GOVERNANCE_ROLES = frozenset({"System Manager", "HRP System Manager"})
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,139}$")


def _repository_root() -> Path:
	return Path(frappe.get_app_path(APP_NAME)).resolve().parent


def _require_governance_reader() -> None:
	if frappe.session.user == "Guest":
		frappe.throw("Authentication required", frappe.AuthenticationError)
	if not GOVERNANCE_ROLES.intersection(frappe.get_roles()):
		frappe.throw("HRP change governance permission is required", frappe.PermissionError)


def _correlation_id(value: str | None) -> str:
	correlation_id = (value or "").strip()
	if not correlation_id:
		request = getattr(frappe.local, "request", None)
		if request is not None:
			correlation_id = (request.headers.get("X-Correlation-ID") or "").strip()
	if not correlation_id:
		correlation_id = frappe.generate_hash(length=16)
	if CORRELATION_ID_PATTERN.fullmatch(correlation_id) is None:
		frappe.throw("Invalid correlation_id", frappe.ValidationError)
	return correlation_id


def get_change_governance_status(correlation_id: str | None = None) -> dict[str, object]:
	"""Return a redacted, read-only view of the Git-governed engineering baseline."""
	_require_governance_reader()
	request_id = _correlation_id(correlation_id)
	try:
		report = inspect_change_governance(_repository_root())
	except ChangeGovernanceError as exc:
		frappe.throw(str(exc), frappe.ValidationError)
	result = report.as_public_dict()
	result["correlation_id"] = request_id
	result["write_channel"] = "Git pull request only"
	result["http_write_enabled"] = False
	frappe.logger("ione_hrp.change_governance", allow_site=True).info(
		{
			"event": "change_governance_status_read",
			"correlation_id": request_id,
			"governance_sha256": report.sha256,
			"decision_count": len(report.decisions),
			"change_record_count": len(report.changes),
		}
	)
	return result
