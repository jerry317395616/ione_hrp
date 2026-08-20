from __future__ import annotations

import frappe

from ione_hrp.common.segregation import (
	SegregationContractError,
	build_segregation_evaluation,
	build_segregation_rule_upsert,
)
from ione_hrp.hrp_workflow_authorization.services.segregation import (
	get_segregation_rule,
	upsert_segregation_rule,
	validate_segregation,
)
from ione_hrp.services.audit_context import service_audit_scope
from ione_hrp.services.errors import raise_ione_error, require_authenticated_user


@frappe.whitelist(allow_guest=True, methods=["POST"])
def validate(
	user: str,
	action: str,
	doctype: str,
	docname: str,
	correlation_id: str | None = None,
) -> dict[str, object]:
	with service_audit_scope(correlation_id):
		require_authenticated_user()
		try:
			command = build_segregation_evaluation(
				user=user,
				action=action,
				doctype=doctype,
				docname=docname,
			)
		except SegregationContractError as exc:
			raise_ione_error("INVALID_REQUEST", cause=exc)
		return validate_segregation(command, correlation_id=correlation_id)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def upsert_rule(
	code: str,
	display_name: str,
	target_doctype: str,
	target_action: str,
	company: str,
	hospital: str,
	valid_from: str,
	actor_fields: str | list[str] | None = None,
	conflicting_roles: str | list[str] | None = None,
	organization_unit: str | None = None,
	include_descendants: bool | int | str = False,
	enabled: bool | int | str = True,
	valid_to: str | None = None,
	expected_revision: int | str = 0,
	rule_name: str | None = None,
	remarks: str | None = None,
	correlation_id: str | None = None,
) -> dict[str, object]:
	with service_audit_scope(correlation_id):
		require_authenticated_user()
		try:
			command = build_segregation_rule_upsert(
				code=code,
				display_name=display_name,
				target_doctype=target_doctype,
				target_action=target_action,
				company=company,
				hospital=hospital,
				organization_unit=organization_unit,
				include_descendants=include_descendants,
				actor_fields=actor_fields,
				conflicting_roles=conflicting_roles,
				enabled=enabled,
				valid_from=valid_from,
				valid_to=valid_to,
				expected_revision=expected_revision,
				rule_name=rule_name,
				remarks=remarks,
			)
		except SegregationContractError as exc:
			raise_ione_error("INVALID_REQUEST", cause=exc)
		return upsert_segregation_rule(command, idempotency_key=None, correlation_id=correlation_id)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_rule(rule_name: str, correlation_id: str | None = None) -> dict[str, object]:
	with service_audit_scope(correlation_id):
		require_authenticated_user()
		if not rule_name:
			raise_ione_error("INVALID_REQUEST")
		return get_segregation_rule(rule_name, correlation_id=correlation_id)


__all__ = ["get_rule", "upsert_rule", "validate"]
