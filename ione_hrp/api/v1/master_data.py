from __future__ import annotations

import frappe

from ione_hrp.common.master_data import (
	MasterDataContractError,
	build_master_data_domain_upsert,
	build_master_data_request_review,
	build_master_data_request_submit,
	build_master_data_request_upsert,
)
from ione_hrp.hrp_master_data.services import (
	get_master_data_request as get_master_data_request_service,
)
from ione_hrp.hrp_master_data.services import (
	review_master_data_request as review_master_data_request_service,
)
from ione_hrp.hrp_master_data.services import (
	save_master_data_request as save_master_data_request_service,
)
from ione_hrp.hrp_master_data.services import (
	submit_master_data_request as submit_master_data_request_service,
)
from ione_hrp.hrp_master_data.services import (
	upsert_master_data_domain as upsert_master_data_domain_service,
)
from ione_hrp.services.audit_context import service_audit_scope
from ione_hrp.services.errors import raise_ione_error


@frappe.whitelist(methods=["POST"])
def upsert_master_data_domain(
	code: str,
	display_name: str,
	target_doctype: str,
	expected_revision: int | str,
	enabled: bool | int | str = True,
	remarks: str | None = None,
	correlation_id: str | None = None,
) -> dict[str, object]:
	with service_audit_scope(correlation_id):
		try:
			command = build_master_data_domain_upsert(
				code=code,
				display_name=display_name,
				target_doctype=target_doctype,
				enabled=enabled,
				expected_revision=expected_revision,
				remarks=remarks,
			)
		except MasterDataContractError as exc:
			raise_ione_error("INVALID_REQUEST", cause=exc)
		return upsert_master_data_domain_service(
			command,
			idempotency_key=None,
			correlation_id=correlation_id,
		)


@frappe.whitelist(methods=["POST"])
def save_master_data_request(
	master_data_domain: str,
	company: str,
	hospital: str,
	organization_unit: str,
	operation: str,
	subject: str,
	effective_on: str,
	changes: str | list[dict[str, object]],
	expected_revision: int | str = 0,
	request_name: str | None = None,
	target_name: str | None = None,
	correlation_id: str | None = None,
) -> dict[str, object]:
	with service_audit_scope(correlation_id):
		try:
			command = build_master_data_request_upsert(
				request_name=request_name,
				master_data_domain=master_data_domain,
				company=company,
				hospital=hospital,
				organization_unit=organization_unit,
				operation=operation,
				target_name=target_name,
				subject=subject,
				effective_on=effective_on,
				changes=changes,
				expected_revision=expected_revision,
			)
		except MasterDataContractError as exc:
			raise_ione_error("INVALID_REQUEST", cause=exc)
		return save_master_data_request_service(
			command,
			idempotency_key=None,
			correlation_id=correlation_id,
		)


@frappe.whitelist(methods=["POST"])
def submit_master_data_request(
	request_name: str,
	expected_revision: int | str,
	correlation_id: str | None = None,
) -> dict[str, object]:
	with service_audit_scope(correlation_id):
		try:
			command = build_master_data_request_submit(
				request_name=request_name,
				expected_revision=expected_revision,
			)
		except MasterDataContractError as exc:
			raise_ione_error("INVALID_REQUEST", cause=exc)
		return submit_master_data_request_service(
			command,
			idempotency_key=None,
			correlation_id=correlation_id,
		)


@frappe.whitelist(methods=["POST"])
def review_master_data_request(
	request_name: str,
	expected_revision: int | str,
	decision: str,
	reason: str | None = None,
	correlation_id: str | None = None,
) -> dict[str, object]:
	with service_audit_scope(correlation_id):
		try:
			command = build_master_data_request_review(
				request_name=request_name,
				expected_revision=expected_revision,
				decision=decision,
				reason=reason,
			)
		except MasterDataContractError as exc:
			raise_ione_error("INVALID_REQUEST", cause=exc)
		return review_master_data_request_service(
			command,
			idempotency_key=None,
			correlation_id=correlation_id,
		)


@frappe.whitelist(methods=["GET"])
def get_master_data_request(
	request_name: str,
	correlation_id: str | None = None,
) -> dict[str, object]:
	return get_master_data_request_service(
		request_name=request_name,
		correlation_id=correlation_id,
	)
