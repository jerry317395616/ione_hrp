# AGENTS.md — ione_hrp single-app repository rules

## Mission
Build a production-grade Hospital Resource Planning platform as one Frappe application (`ione_hrp`) with multiple Frappe modules. Target the pinned GitHub `develop` commits recorded in `resolved_versions.lock.json`.

## Source and dependency rules
- One custom app only: `ione_hrp`. Do not create additional `ione_hrp_*` apps without an approved ADR.
- Never edit or fork product features into `frappe`, `erpnext`, or `hrms`.
- The floating `develop` branches are used only during the explicit baseline-refresh workflow. Normal work uses locked commit SHAs.
- Keep `pyproject.toml`, `modules.txt`, `architecture/module_registry.yaml`, module directories and Module Def records consistent.
- New business areas are created as modules inside `ione_hrp`, not as new apps.

## Frappe integrity rules
- Prefer standard configuration, fixtures, Custom Fields, `extend_doctype_class`, `doc_events`, and typed domain services, in that order.
- `override_doctype_class` requires an accepted ADR.
- Never write directly to `GL Entry`, `Stock Ledger Entry`, `Bin`, submitted ERPNext/HRMS documents, or immutable HRP ledgers.
- Use standard document controllers, cancellation/amendment flows, or append-only reversal records.
- `docstatus` is lifecycle; `workflow_state` is approval state. Do not conflate them.
- Never call external systems inside a database transaction. Persist Outbox in the transaction and send after commit.
- Do not call `frappe.db.commit()` from document hooks or domain services.

## Module structure
Each module lives at `ione_hrp/<module_package>/` and may contain:
- `doctype/`
- `report/`
- `page/`
- `workspace/`
- `services/`
- `api/`
- `tests/`

Shared code belongs in `ione_hrp/common`, `ione_hrp/services`, or `ione_hrp/integrations`; do not create circular imports between modules.

## Security and audit
- Every write API requires authentication, role/data-scope checks, idempotency where retried, transaction boundaries, correlation IDs and audit evidence.
- Every organization-scoped query must use the reviewed scope helper.
- AI is read-only by default. Posting, payment, approval, master-data mutation and other high-risk actions require persisted human confirmation.
- Never log credentials, tokens, patient identifiers, invoice images or sensitive payloads.

## Implementation workflow
1. Read one `COD-XXX` backlog row and all linked design artifacts.
2. State impacted module, DocTypes, services, hooks, APIs, migrations, permissions and tests.
3. Implement one vertical slice: model → service → permission/workflow → API/UI → tests → docs.
4. Run `scripts/validate_package.py`, Ruff/type checks and relevant Frappe tests.
5. Update fixtures, patches, blueprints, ADRs and documentation in the same change.

## Completion response
Return changed files, migrations, tests and results, permission impact, data/upgrade risks, rollback steps, unresolved decisions and the next unblocked task.
