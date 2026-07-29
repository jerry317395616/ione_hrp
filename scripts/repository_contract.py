from __future__ import annotations

import ast
import csv
import json
import re
import sys
from pathlib import Path

import tomllib
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
	sys.path.insert(0, str(REPOSITORY_ROOT))

from ione_hrp.common.change_governance import (
	ChangeGovernanceError,
	inspect_change_governance,
)
from ione_hrp.common.environment_profiles import (
	EnvironmentProfileError,
	load_environment_registry,
)
from ione_hrp.common.error_catalog import (
	ErrorCatalogError,
	load_error_catalog,
	validate_error_translations,
)
from ione_hrp.common.fixture_policy import (
	FixturePolicyError,
	inspect_fixture_repository,
	load_fixture_policy,
)
from ione_hrp.common.immutable_ledger import BASE_LEDGER_FIELDS
from ione_hrp.common.test_data_factory import (
	TestDataFactoryContractError,
	load_test_data_scenario_registry,
)
from ione_hrp.common.transactional_message import BASE_MESSAGE_FIELDS
from ione_hrp.services.module_registry import validate_module_source_tree

if __package__:
	from scripts.version_lock import UPSTREAM_APPS, load_lock
else:
	from version_lock import UPSTREAM_APPS, load_lock

APP_NAME = "ione_hrp"
UPSTREAM_APPS = frozenset({"frappe", "erpnext", "hrms"})
REQUIRED_CI_CONTEXT = "Required"
REQUIRED_CI_JOBS = frozenset({"quality", "integration", "required"})
REQUIRED_PYTHON_DEV_DEPENDENCIES = frozenset({"pyyaml==6.0.3", "ruff==0.15.9"})
LEGACY_PREFIXES = ("myi" + "_hrp", "myi" + "-hrp")
PROTECTED_LEDGER_PATTERNS = (
	re.compile(r"""(?:new_doc|get_doc)\(\s*["']GL Entry["']"""),
	re.compile(r"""(?:new_doc|get_doc)\(\s*["']Stock Ledger Entry["']"""),
	re.compile(r"""(?:new_doc|get_doc)\(\s*["']Bin["']"""),
	re.compile(r"""tab(?:GL Entry|Stock Ledger Entry|Bin)"""),
)
IMMUTABLE_LEDGER_FORBIDDEN_PERMISSIONS = (
	"create",
	"write",
	"delete",
	"submit",
	"cancel",
	"amend",
	"import",
)
REQUIRED_NODE_DEV_DEPENDENCIES = frozenset(
	{
		"@eslint/js",
		"eslint",
		"eslint-config-prettier",
		"eslint-plugin-vue",
		"globals",
		"prettier",
		"pyright",
		"typescript",
		"typescript-eslint",
	}
)
REQUIRED_NODE_SCRIPTS = frozenset(
	{
		"format:frontend",
		"format:frontend:check",
		"lint:frontend",
		"quality",
		"quality:node",
		"typecheck",
	}
)
EXCLUDED_REPOSITORY_PARTS = frozenset(
	{
		".git",
		".mypy_cache",
		".pyright",
		".pytest_cache",
		".ruff_cache",
		".venv",
		"__pycache__",
		"build",
		"dist",
		"node_modules",
		"venv",
	}
)
TEXT_SUFFIXES = {
	".csv",
	".html",
	".json",
	".md",
	".py",
	".sh",
	".svg",
	".toml",
	".txt",
	".yaml",
	".yml",
}
BASELINE_ERROR_CODES = {
	"AUTHENTICATION_REQUIRED": "IONE-CORE-0001",
	"PERMISSION_DENIED": "IONE-CORE-0002",
	"INVALID_REQUEST": "IONE-CORE-0003",
	"RESOURCE_NOT_FOUND": "IONE-CORE-0004",
	"CONFLICT": "IONE-CORE-0005",
	"INVALID_STATE_TRANSITION": "IONE-CORE-0006",
	"IDEMPOTENCY_CONFLICT": "IONE-CORE-0007",
	"OPERATION_NOT_ALLOWED": "IONE-CORE-0008",
	"CONFIGURATION_INVALID": "IONE-CORE-0009",
	"DEPENDENCY_UNAVAILABLE": "IONE-CORE-0010",
	"RATE_LIMITED": "IONE-CORE-0011",
	"INTERNAL_ERROR": "IONE-CORE-0012",
}


def discover_custom_apps(root: Path) -> dict[str, Path]:
	discovered: dict[str, Path] = {}
	for pyproject_path in root.rglob("pyproject.toml"):
		if EXCLUDED_REPOSITORY_PARTS.intersection(pyproject_path.parts):
			continue
		payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
		project_name = payload.get("project", {}).get("name")
		if project_name:
			discovered[str(project_name)] = pyproject_path.parent
	return discovered


def iter_repository_text_files(root: Path):
	for path in root.rglob("*"):
		if (
			not path.is_file()
			or EXCLUDED_REPOSITORY_PARTS.intersection(path.parts)
			or path.name in {"SHA256SUMS.txt", ".eslintcache"}
		):
			continue
		if path.suffix.lower() in TEXT_SUFFIXES:
			yield path


def find_legacy_prefix_references(root: Path) -> list[str]:
	findings: list[str] = []
	for path in iter_repository_text_files(root):
		text = path.read_text(encoding="utf-8")
		for prefix in LEGACY_PREFIXES:
			if prefix in text:
				findings.append(f"{path.relative_to(root)} contains {prefix}")
	return findings


def validate_branch_policy(root: Path) -> list[str]:
	policy_path = root / ".github" / "branch-protection.json"
	if not policy_path.is_file():
		return ["missing .github/branch-protection.json"]
	policy = json.loads(policy_path.read_text(encoding="utf-8"))
	protection = policy.get("protection", {})
	reviews = protection.get("required_pull_request_reviews")
	violations: list[str] = []
	if policy.get("default_branch") != "main":
		violations.append("default branch must be main")
	if protection.get("enforce_admins") is not True:
		violations.append("branch protection must include administrators")
	required_checks = protection.get("required_status_checks")
	if not isinstance(required_checks, dict):
		violations.append("branch protection must require CI status checks")
	else:
		if required_checks.get("strict") is not True:
			violations.append("required CI checks must use the latest main branch")
		if required_checks.get("contexts") != [REQUIRED_CI_CONTEXT]:
			violations.append(f"branch protection must require only {REQUIRED_CI_CONTEXT}")
	if not isinstance(reviews, dict):
		violations.append("pull requests must be required before merging")
	if protection.get("allow_force_pushes") is not False:
		violations.append("force pushes must be disabled")
	if protection.get("allow_deletions") is not False:
		violations.append("protected branch deletion must be disabled")
	return violations


def validate_push_guard(root: Path) -> list[str]:
	hook_path = root / ".githooks" / "pre-push"
	if not hook_path.is_file():
		return ["missing .githooks/pre-push"]
	hook = hook_path.read_text(encoding="utf-8")
	violations: list[str] = []
	if "refs/heads/main" not in hook:
		violations.append("pre-push hook must guard refs/heads/main")
	if "exit 1" not in hook:
		violations.append("pre-push hook must reject direct main pushes")
	if not (root / "scripts" / "apply_branch_protection.py").is_file():
		violations.append("missing scripts/apply_branch_protection.py")
	return violations


def validate_quality_tooling(root: Path) -> list[str]:
	violations: list[str] = []
	required_files = (
		".npmrc",
		".prettierignore",
		".prettierrc.json",
		"eslint.config.mjs",
		"package-lock.json",
		"package.json",
		"pyrightconfig.json",
		"scripts/quality.py",
		"scripts/quality.sh",
	)
	for relative_path in required_files:
		if not (root / relative_path).is_file():
			violations.append(f"missing quality configuration: {relative_path}")
	if violations:
		return violations

	pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
	dev_extras = pyproject.get("project", {}).get("optional-dependencies", {}).get("dev", [])
	if set(dev_extras) != REQUIRED_PYTHON_DEV_DEPENDENCIES:
		violations.append(
			"project.optional-dependencies.dev must be exactly "
			+ ", ".join(sorted(REQUIRED_PYTHON_DEV_DEPENDENCIES))
		)
	ruff = pyproject.get("tool", {}).get("ruff", {})
	if ruff.get("target-version") != "py310":
		violations.append("Ruff target-version must match the Python 3.10 application baseline")

	package = json.loads((root / "package.json").read_text(encoding="utf-8"))
	dev_dependencies = package.get("devDependencies", {})
	if set(dev_dependencies) != REQUIRED_NODE_DEV_DEPENDENCIES:
		violations.append(
			"package.json devDependencies must be exactly "
			+ ", ".join(sorted(REQUIRED_NODE_DEV_DEPENDENCIES))
		)
	for dependency, version in dev_dependencies.items():
		if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-.][0-9A-Za-z]+)*", str(version)):
			violations.append(f"quality dependency must use an exact version: {dependency}={version}")
	scripts = package.get("scripts", {})
	missing_scripts = sorted(REQUIRED_NODE_SCRIPTS - set(scripts))
	if missing_scripts:
		violations.append("package.json is missing scripts: " + ", ".join(missing_scripts))
	if scripts.get("quality") != "python scripts/quality.py":
		violations.append("package.json quality must invoke scripts/quality.py")
	if not re.fullmatch(r"npm@\d+\.\d+\.\d+", str(package.get("packageManager", ""))):
		violations.append("packageManager must pin an exact npm version")

	lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
	locked_root = lock.get("packages", {}).get("", {})
	if locked_root.get("devDependencies") != dev_dependencies:
		violations.append("package-lock.json root devDependencies differ from package.json")

	pyright = json.loads((root / "pyrightconfig.json").read_text(encoding="utf-8"))
	if not {"ione_hrp", "scripts", "tests"}.issubset(set(pyright.get("include", []))):
		violations.append("Pyright must include ione_hrp, scripts and tests")
	if pyright.get("pythonVersion") != "3.10":
		violations.append("Pyright pythonVersion must match the Python 3.10 baseline")
	if pyright.get("typeCheckingMode") not in {"basic", "standard", "strict"}:
		violations.append("Pyright typeCheckingMode must not be off")

	quality_shell = (root / "scripts" / "quality.sh").read_text(encoding="utf-8")
	if "scripts/quality.py" not in quality_shell:
		violations.append("scripts/quality.sh must delegate to scripts/quality.py")
	if "command -v ruff" in quality_shell:
		violations.append("quality checks must fail instead of silently skipping missing Ruff")
	return violations


def validate_ci_pipeline(root: Path) -> list[str]:
	workflow_path = root / ".github" / "workflows" / "ci.yml"
	integration_script_path = root / "scripts" / "ci_integration.sh"
	violations: list[str] = []
	if not workflow_path.is_file():
		violations.append("missing .github/workflows/ci.yml")
	if not integration_script_path.is_file():
		violations.append("missing scripts/ci_integration.sh")
	if violations:
		return violations

	workflow_text = workflow_path.read_text(encoding="utf-8")
	try:
		workflow = yaml.load(workflow_text, Loader=yaml.BaseLoader)
	except yaml.YAMLError as exc:
		return [f"invalid CI workflow YAML: {exc}"]
	if not isinstance(workflow, dict):
		return ["CI workflow must be a mapping"]

	if workflow.get("name") != "CI":
		violations.append("CI workflow name must remain CI")
	triggers = workflow.get("on")
	if not isinstance(triggers, dict):
		violations.append("CI workflow triggers must be a mapping")
	else:
		required_triggers = {"pull_request", "push", "workflow_dispatch"}
		if not required_triggers.issubset(triggers):
			violations.append("CI must run for pull requests, main pushes and manual dispatch")
		if "pull_request_target" in triggers:
			violations.append("CI must not use pull_request_target")
		push = triggers.get("push")
		if not isinstance(push, dict) or push.get("branches") != ["main"]:
			violations.append("CI push trigger must be restricted to main")

	permissions = workflow.get("permissions")
	if permissions != {"contents": "read"}:
		violations.append("CI workflow permissions must be contents: read only")
	if "secrets." in workflow_text:
		violations.append("CI must not consume repository secrets")

	concurrency = workflow.get("concurrency")
	if not isinstance(concurrency, dict) or concurrency.get("cancel-in-progress") != "true":
		violations.append("CI must cancel superseded runs")

	jobs = workflow.get("jobs")
	if not isinstance(jobs, dict):
		return [*violations, "CI workflow jobs must be a mapping"]
	missing_jobs = sorted(REQUIRED_CI_JOBS - set(jobs))
	if missing_jobs:
		violations.append("CI workflow is missing jobs: " + ", ".join(missing_jobs))
		return violations

	expected_names = {
		"quality": "Quality",
		"integration": "Integration",
		"required": "Required",
	}
	for job_name, display_name in expected_names.items():
		job = jobs.get(job_name)
		if not isinstance(job, dict) or job.get("name") != display_name:
			violations.append(f"CI job {job_name} must keep stable name {display_name}")
			continue
		timeout = job.get("timeout-minutes")
		if not isinstance(timeout, str) or not timeout.isdigit() or int(timeout) <= 0:
			violations.append(f"CI job {job_name} must define a positive timeout")

	integration = jobs["integration"]
	if isinstance(integration, dict):
		if integration.get("needs") != "quality":
			violations.append("CI integration job must depend on quality")
		services = integration.get("services")
		mariadb = services.get("mariadb") if isinstance(services, dict) else None
		if not isinstance(mariadb, dict) or mariadb.get("image") != "mariadb:11.8":
			violations.append("CI integration job must use MariaDB 11.8")

	required = jobs["required"]
	if isinstance(required, dict):
		if set(required.get("needs", [])) != {"quality", "integration"}:
			violations.append("CI required job must aggregate quality and integration")
		if required.get("if") != "always()":
			violations.append("CI required job must run with always()")

	action_pattern = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$")
	actions: list[str] = []
	for job_name, job in jobs.items():
		if not isinstance(job, dict):
			continue
		for step in job.get("steps", []):
			if not isinstance(step, dict):
				continue
			action = step.get("uses")
			if action:
				actions.append(str(action))
			if action and not str(action).startswith("./") and not action_pattern.fullmatch(str(action)):
				violations.append(f"CI action must pin a full commit SHA: {job_name}: {action}")
	if not any(action.startswith("gitleaks/gitleaks-action@") for action in actions):
		violations.append("CI quality job must scan repository history with Gitleaks")

	quality = jobs["quality"]
	quality_commands = "\n".join(
		str(step.get("run", "")) for step in quality.get("steps", []) if isinstance(step, dict)
	)
	for required_command in (
		'pip install --disable-pip-version-check -e ".[dev]"',
		"npm ci",
		"python scripts/quality.py",
		"python scripts/change_manager.py",
		"npm audit --audit-level=high",
	):
		if required_command not in quality_commands:
			violations.append(f"CI quality job is missing command: {required_command}")

	integration_commands = "\n".join(
		str(step.get("run", "")) for step in integration.get("steps", []) if isinstance(step, dict)
	)
	if "bash scripts/ci_integration.sh" not in integration_commands:
		violations.append("CI integration job must invoke scripts/ci_integration.sh")

	integration_script = integration_script_path.read_text(encoding="utf-8")
	for required_token in (
		"bootstrap_latest_develop.sh",
		"KEEP_TEMPORARY_REDIS=1",
		"version_lock.py",
		"migrate --skip-search-index",
		"run-tests --app ione_hrp",
		"SELECT COUNT(*) FROM `tabError Log`",
		"git -C",
	):
		if required_token not in integration_script:
			violations.append(f"CI integration script is missing: {required_token}")
	return violations


def validate_version_baseline(root: Path) -> list[str]:
	violations: list[str] = []
	try:
		lock = load_lock(root / "resolved_versions.lock.json")
	except ValueError as exc:
		return [f"invalid resolved_versions.lock.json: {exc}"]

	baseline_path = root / "architecture" / "version_baseline.json"
	if not baseline_path.is_file():
		return ["missing architecture/version_baseline.json"]
	baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
	if baseline.get("lock_file") != "../resolved_versions.lock.json":
		violations.append("version baseline must reference resolved_versions.lock.json")
	rows = baseline.get("repositories")
	if not isinstance(rows, dict):
		return [*violations, "version baseline repositories must be an object"]
	for app in UPSTREAM_APPS:
		baseline_row = rows.get(app)
		if not isinstance(baseline_row, dict):
			violations.append(f"version baseline is missing {app}")
			continue
		for field in ("url", "branch", "version_marker", "commit"):
			lock_field = "repository" if field == "url" else "version" if field == "version_marker" else field
			if baseline_row.get(field) != lock["apps"][app].get(lock_field):
				violations.append(f"version baseline {app}.{field} differs from lock")
	return violations


def validate_catalog_ownership(root: Path) -> list[str]:
	violations: list[str] = []
	csv_catalogs = (
		root / "design" / "doctype_catalog.csv",
		root / "design" / "field_catalog.csv",
		root / "api" / "api_catalog.csv",
		root / "backlog" / "backlog.csv",
	)
	for path in csv_catalogs:
		with path.open(encoding="utf-8-sig", newline="") as handle:
			apps = {row.get("app", "") for row in csv.DictReader(handle)}
		if apps != {APP_NAME}:
			violations.append(f"{path.relative_to(root)} app values are {sorted(apps)}")

	for path in (root / "doctype_blueprints").rglob("*.json"):
		payload = json.loads(path.read_text(encoding="utf-8"))
		if payload.get("x_hrp", {}).get("app") != APP_NAME:
			violations.append(f"{path.relative_to(root)} has wrong x_hrp.app")
	return violations


def validate_module_structure(root: Path) -> list[str]:
	return validate_module_source_tree(root, expected_module_count=36)


def validate_module_boundaries(root: Path) -> list[str]:
	"""Require cross-module Python imports to use the target module's services facade."""
	package_root = root / APP_NAME
	violations: list[str] = []
	if not package_root.is_dir():
		return [f"missing {APP_NAME} package directory"]
	module_pattern = re.compile(r"^ione_hrp\.(hrp_[a-z0-9_]+)(?:\.(.+))?$")
	for source_root in package_root.iterdir():
		if not source_root.is_dir() or not source_root.name.startswith("hrp_"):
			continue
		for path in source_root.rglob("*.py"):
			try:
				tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
			except SyntaxError:
				continue
			imports: list[str] = []
			for node in ast.walk(tree):
				if isinstance(node, ast.ImportFrom) and node.module:
					imports.append(node.module)
				elif isinstance(node, ast.Import):
					imports.extend(alias.name for alias in node.names)
			for imported in imports:
				match = module_pattern.match(imported)
				if not match:
					continue
				target_package, target_path = match.groups()
				if target_package == source_root.name:
					continue
				if target_path and target_path.split(".", 1)[0] == "services":
					continue
				violations.append(
					f"{path.relative_to(root)} imports private cross-module path {imported}; "
					f"use ione_hrp.{target_package}.services"
				)
	return violations


def validate_protected_ledgers(root: Path) -> list[str]:
	app_root = root / APP_NAME
	violations: list[str] = []
	for path in app_root.rglob("*.py"):
		text = path.read_text(encoding="utf-8")
		for pattern in PROTECTED_LEDGER_PATTERNS:
			if pattern.search(text):
				violations.append(
					f"{path.relative_to(root)} contains forbidden protected-ledger write pattern"
				)
				break
	return violations


def find_direct_frappe_throws(root: Path) -> list[str]:
	"""Keep one application-level adapter for Frappe error and permission helpers."""
	app_root = root / APP_NAME
	allowed_path = app_root / "services" / "errors.py"
	forbidden_helpers = frozenset({"only_for", "throw"})
	violations: list[str] = []
	if not app_root.is_dir():
		return [f"missing {APP_NAME} package directory"]
	for path in app_root.rglob("*.py"):
		if path == allowed_path:
			continue
		try:
			tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		except SyntaxError:
			continue
		imported_helpers = {
			alias.asname or alias.name: alias.name
			for node in ast.walk(tree)
			if isinstance(node, ast.ImportFrom) and node.module == "frappe"
			for alias in node.names
			if alias.name in forbidden_helpers
		}
		for node in ast.walk(tree):
			if not isinstance(node, ast.Call):
				continue
			helper_name: str | None = None
			if (
				isinstance(node.func, ast.Attribute)
				and isinstance(node.func.value, ast.Name)
				and node.func.value.id == "frappe"
				and node.func.attr in forbidden_helpers
			):
				helper_name = node.func.attr
			elif isinstance(node.func, ast.Name):
				helper_name = imported_helpers.get(node.func.id)
			if helper_name is not None:
				violations.append(
					f"{path.relative_to(root)}:{node.lineno} calls frappe.{helper_name} outside "
					"ione_hrp.services.errors"
				)
	return violations


def validate_error_contract(root: Path) -> list[str]:
	catalog_path = root / APP_NAME / "config" / "error_catalog.json"
	translation_path = root / APP_NAME / "translations" / "zh.csv"
	common_path = root / APP_NAME / "common" / "error_catalog.py"
	service_path = root / APP_NAME / "services" / "errors.py"
	api_path = root / APP_NAME / "api" / "v1" / "errors.py"
	documentation_path = root / "architecture" / "errors.md"
	task_path = root / "backlog" / "COD-009.md"
	catalog_paths = (
		root / "api" / "api_catalog.csv",
		root / "api" / "api_catalog.yaml",
		root / "api" / "openapi.yaml",
	)
	required_paths = (
		catalog_path,
		translation_path,
		common_path,
		service_path,
		api_path,
		documentation_path,
		task_path,
		*catalog_paths,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.is_file()]
	if missing:
		return [f"missing error contract file: {path}" for path in missing]

	try:
		catalog = load_error_catalog(catalog_path)
		validate_error_translations(catalog, translation_path)
	except ErrorCatalogError as exc:
		return [f"invalid error contract: {exc}"]

	violations = find_direct_frappe_throws(root)
	actual_baseline = {key: catalog.get(key).code for key in BASELINE_ERROR_CODES if key in catalog.by_key}
	if actual_baseline != BASELINE_ERROR_CODES:
		violations.append("error catalog must preserve all baseline IONE-CORE error codes")

	service_text = service_path.read_text(encoding="utf-8")
	for token in (
		'"ione_error"',
		'"X-Ione-Error-Code"',
		'"X-Ione-Error-ID"',
		'"ione_hrp.errors"',
		"http_write_enabled",
	):
		if token not in service_text:
			violations.append(f"error service is missing contract token: {token}")

	error_api = "/api/method/ione_hrp.api.v1.errors.get_error_catalog"
	for catalog_file in catalog_paths:
		if error_api not in catalog_file.read_text(encoding="utf-8"):
			violations.append(f"{catalog_file.relative_to(root)} is missing the error catalog endpoint")
	api_text = api_path.read_text(encoding="utf-8")
	if '@frappe.whitelist(allow_guest=True, methods=["GET"])' not in api_text:
		violations.append("error catalog endpoint must enter the application layer for uniform guest errors")
	if "IoneError" not in (root / "api" / "openapi.yaml").read_text(encoding="utf-8"):
		violations.append("OpenAPI must define the IoneError response schema")
	return violations


def find_direct_audit_loggers(root: Path) -> list[str]:
	"""Require application audit events to pass through the redacting context service."""
	app_root = root / APP_NAME
	allowed_path = app_root / "services" / "audit_context.py"
	violations: list[str] = []
	for path in app_root.rglob("*.py"):
		if path == allowed_path or "tests" in path.parts:
			continue
		try:
			tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		except SyntaxError:
			continue
		for node in ast.walk(tree):
			if (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Attribute)
				and isinstance(node.func.value, ast.Name)
				and node.func.value.id == "frappe"
				and node.func.attr == "logger"
			):
				violations.append(
					f"{path.relative_to(root)}:{node.lineno} calls frappe.logger outside "
					"ione_hrp.services.audit_context"
				)
	return violations


def find_direct_transaction_commits(root: Path) -> list[str]:
	"""Keep the final transaction commit owned by the Frappe request or job."""
	app_root = root / APP_NAME
	violations: list[str] = []
	if not app_root.is_dir():
		return [f"missing {APP_NAME} package directory"]
	for path in app_root.rglob("*.py"):
		try:
			tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		except SyntaxError:
			continue
		for node in ast.walk(tree):
			if (
				isinstance(node, ast.Call)
				and isinstance(node.func, ast.Attribute)
				and node.func.attr == "commit"
				and isinstance(node.func.value, ast.Attribute)
				and node.func.value.attr == "db"
				and isinstance(node.func.value.value, ast.Name)
				and node.func.value.value.id == "frappe"
			):
				violations.append(
					f"{path.relative_to(root)}:{node.lineno} calls frappe.db.commit; "
					"the outer Frappe transaction owns the commit"
				)
	return violations


def validate_audit_context_contract(root: Path) -> list[str]:
	common_path = root / APP_NAME / "common" / "audit_context.py"
	service_path = root / APP_NAME / "services" / "audit_context.py"
	api_path = root / APP_NAME / "api" / "v1" / "audit.py"
	hooks_path = root / APP_NAME / "hooks.py"
	documentation_path = root / "architecture" / "audit_context.md"
	task_path = root / "backlog" / "COD-010.md"
	test_paths = (
		root / "tests" / "test_audit_context.py",
		root / APP_NAME / "hrp_foundation" / "tests" / "test_audit_context.py",
	)
	catalog_paths = (
		root / "api" / "api_catalog.csv",
		root / "api" / "api_catalog.yaml",
		root / "api" / "openapi.yaml",
	)
	required_paths = (
		common_path,
		service_path,
		api_path,
		hooks_path,
		documentation_path,
		task_path,
		*test_paths,
		*catalog_paths,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.is_file()]
	if missing:
		return [f"missing audit context contract file: {path}" for path in missing]

	violations = find_direct_audit_loggers(root)
	hooks_text = hooks_path.read_text(encoding="utf-8")
	for token in (
		"start_http_audit_context",
		"finish_http_audit_context",
		"start_job_audit_context",
		"finish_job_audit_context",
	):
		if token not in hooks_text:
			violations.append(f"Frappe hooks are missing audit lifecycle token: {token}")

	common_text = common_path.read_text(encoding="utf-8")
	for token in (
		"AUDIT_CONTEXT_SCHEMA_VERSION = 1",
		"class AuditContext",
		"as_propagation_dict",
		"parse_propagation_payload",
		"FORBIDDEN_AUDIT_FIELD_MARKERS",
	):
		if token not in common_text:
			violations.append(f"audit context model is missing: {token}")

	service_text = service_path.read_text(encoding="utf-8")
	for token in (
		'"X-Correlation-ID"',
		'"X-Request-ID"',
		"AUDIT_CONTEXT_JOB_KWARG",
		"kwargs.pop(AUDIT_CONTEXT_JOB_KWARG",
		"emit_audit_event",
		"enqueue_with_audit",
		"http_write_enabled",
	):
		if token not in service_text:
			violations.append(f"audit context service is missing: {token}")

	api_text = api_path.read_text(encoding="utf-8")
	if '@frappe.whitelist(allow_guest=True, methods=["GET"])' not in api_text:
		violations.append("audit context endpoint must enter the application layer for uniform guest errors")

	audit_api = "/api/method/ione_hrp.api.v1.audit.get_audit_context"
	for catalog_path in catalog_paths:
		if audit_api not in catalog_path.read_text(encoding="utf-8"):
			violations.append(f"{catalog_path.relative_to(root)} is missing the audit context endpoint")

	openapi_text = (root / "api" / "openapi.yaml").read_text(encoding="utf-8")
	for token in ("X-Correlation-ID", "X-Request-ID", "AuditContext", "correlation_id", "request_id"):
		if token not in openapi_text:
			violations.append(f"OpenAPI is missing audit context token: {token}")

	for script_name in ("change_manager.py", "environment_manager.py", "fixture_manager.py"):
		script_text = (root / "scripts" / script_name).read_text(encoding="utf-8")
		if "ione_hrp.common.audit_context" not in script_text:
			violations.append(f"{script_name} must use the shared correlation ID contract")
		if "CORRELATION_ID_PATTERN" in script_text:
			violations.append(f"{script_name} must not define a duplicate correlation ID pattern")

	for path in (root / APP_NAME).rglob("*.py"):
		if path == service_path or "tests" in path.parts:
			continue
		text = path.read_text(encoding="utf-8")
		if "X-Correlation-ID" in text:
			violations.append(
				f"{path.relative_to(root)} reads X-Correlation-ID outside the audit context service"
			)
		if "CORRELATION_ID_PATTERN" in text:
			violations.append(f"{path.relative_to(root)} defines a duplicate correlation ID pattern")
	return violations


def validate_domain_service_contract(root: Path) -> list[str]:
	common_path = root / APP_NAME / "common" / "domain_service.py"
	service_path = root / APP_NAME / "services" / "domain_service.py"
	idempotency_path = root / APP_NAME / "services" / "idempotency.py"
	doctype_root = root / APP_NAME / "hrp_foundation" / "doctype" / "hrp_service_idempotency"
	doctype_json_path = doctype_root / "hrp_service_idempotency.json"
	doctype_controller_path = doctype_root / "hrp_service_idempotency.py"
	facade_path = root / APP_NAME / "hrp_foundation" / "services" / "__init__.py"
	example_service_path = root / APP_NAME / "hrp_foundation" / "services" / "module_settings.py"
	api_path = root / APP_NAME / "api" / "v1" / "modules.py"
	documentation_path = root / "architecture" / "domain_services.md"
	adr_path = root / "architecture" / "adr" / "ADR-0006-domain-service-and-durable-idempotency.md"
	task_path = root / "backlog" / "COD-011.md"
	change_path = root / "changes" / "COD-011.json"
	test_paths = (
		root / "tests" / "test_domain_service.py",
		root / APP_NAME / "hrp_foundation" / "tests" / "test_domain_service.py",
		root / APP_NAME / "hrp_foundation" / "tests" / "test_modules.py",
	)
	catalog_paths = (
		root / "api" / "api_catalog.csv",
		root / "api" / "api_catalog.yaml",
		root / "api" / "openapi.yaml",
	)
	required_paths = (
		common_path,
		service_path,
		idempotency_path,
		doctype_json_path,
		doctype_controller_path,
		facade_path,
		example_service_path,
		api_path,
		documentation_path,
		adr_path,
		task_path,
		change_path,
		*test_paths,
		*catalog_paths,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.is_file()]
	if missing:
		return [f"missing domain service contract file: {path}" for path in missing]

	violations = find_direct_transaction_commits(root)

	common_text = common_path.read_text(encoding="utf-8")
	for token in (
		"class DomainServiceDefinition",
		"class DomainServiceExecution",
		"canonical_json_object",
		"idempotency_key_hash",
		"idempotency_record_name",
		"MAX_JSON_SNAPSHOT_BYTES",
	):
		if token not in common_text:
			violations.append(f"domain service model is missing: {token}")

	service_text = service_path.read_text(encoding="utf-8")
	for token in (
		"class DomainService",
		"require_roles",
		"frappe.db.savepoint",
		"frappe.db.rollback",
		"reserve_idempotency",
		"complete_idempotency",
		"domain_service_started",
		"domain_service_completed",
		"domain_service_replayed",
		"domain_service_failed",
	):
		if token not in service_text:
			violations.append(f"domain service template is missing: {token}")

	idempotency_text = idempotency_path.read_text(encoding="utf-8")
	for token in (
		'request.headers.get("Idempotency-Key")',
		"idempotency_key_hash",
		"request_fingerprint",
		"response_fingerprint",
		"encrypt(serialized)",
		"decrypt(record.response_snapshot)",
		'raise_ione_error("IDEMPOTENCY_CONFLICT")',
	):
		if token not in idempotency_text:
			violations.append(f"idempotency service is missing: {token}")

	doctype_payload = json.loads(doctype_json_path.read_text(encoding="utf-8"))
	if doctype_payload.get("module") != "HRP Foundation":
		violations.append("HRP Service Idempotency must belong to HRP Foundation")
	fields = {
		str(field.get("fieldname")): field
		for field in doctype_payload.get("fields", [])
		if isinstance(field, dict)
	}
	for forbidden_field in ("idempotency_key", "request_payload", "request_snapshot"):
		if forbidden_field in fields:
			violations.append(f"HRP Service Idempotency must not persist plaintext field {forbidden_field}")
	response_snapshot = fields.get("response_snapshot", {})
	if (
		response_snapshot.get("fieldtype") != "Long Text"
		or response_snapshot.get("hidden") != 1
		or response_snapshot.get("read_only") != 1
		or response_snapshot.get("no_copy") != 1
	):
		violations.append("encrypted response_snapshot must be hidden, read-only and non-copyable")
	allowed_permission_keys = {"role", "read", "report", "select"}
	for permission in doctype_payload.get("permissions", []):
		if not isinstance(permission, dict):
			violations.append("HRP Service Idempotency contains an invalid permission row")
			continue
		if permission.get("role") not in {"System Manager", "HRP System Manager"}:
			violations.append("HRP Service Idempotency has an unauthorized role")
		if any(key not in allowed_permission_keys and bool(value) for key, value in permission.items()):
			violations.append("HRP Service Idempotency permissions must be read-only")

	facade_text = facade_path.read_text(encoding="utf-8")
	if "set_module_enabled" not in facade_text:
		violations.append("HRP Foundation facade must expose the module command")
	api_text = api_path.read_text(encoding="utf-8")
	if "set_module_enabled_service" not in api_text:
		violations.append("module write API must delegate to the HRP Foundation service facade")
	if ".save(" in api_text:
		violations.append("module write API must not save DocTypes directly")
	api_tree = ast.parse(api_text, filename=str(api_path))
	module_write_functions = [
		node
		for node in api_tree.body
		if isinstance(node, ast.FunctionDef) and node.name == "set_module_enabled"
	]
	if len(module_write_functions) != 1:
		violations.append("module write API must define exactly one set_module_enabled endpoint")
	elif "idempotency_key" in {argument.arg for argument in module_write_functions[0].args.args}:
		violations.append("HTTP idempotency keys must be accepted only through the request header")

	module_api = "/api/method/ione_hrp.api.v1.modules.set_module_enabled"
	for catalog_path in catalog_paths:
		catalog_text = catalog_path.read_text(encoding="utf-8")
		if module_api not in catalog_text:
			violations.append(
				f"{catalog_path.relative_to(root)} is missing the domain service example endpoint"
			)
		if "Idempotency-Key" not in catalog_text:
			violations.append(f"{catalog_path.relative_to(root)} is missing the idempotency header contract")

	openapi_payload = yaml.safe_load((root / "api" / "openapi.yaml").read_text(encoding="utf-8"))
	operation = openapi_payload.get("paths", {}).get(module_api, {}).get("post", {})
	idempotency_headers = [
		parameter
		for parameter in operation.get("parameters", [])
		if isinstance(parameter, dict)
		and parameter.get("in") == "header"
		and parameter.get("name") == "Idempotency-Key"
	]
	if len(idempotency_headers) != 1 or idempotency_headers[0].get("required") is not True:
		violations.append("PLT-009 OpenAPI must require exactly one Idempotency-Key header")
	if operation.get("x-idempotency") != "Required for write; encrypted response snapshot":
		violations.append("PLT-009 OpenAPI must declare durable encrypted idempotency")
	return violations


def find_direct_immutable_ledger_bypasses(root: Path) -> list[str]:
	"""Keep concrete HRP ledger access behind the shared immutable-ledger service."""
	app_root = root / APP_NAME
	allowed_path = app_root / "services" / "immutable_ledger.py"
	ledger_pattern = re.compile(r"^HRP [A-Za-z0-9][A-Za-z0-9 -]{1,134} Ledger$")
	forbidden_calls = frozenset(
		{
			"frappe.delete_doc",
			"frappe.get_doc",
			"frappe.new_doc",
			"frappe.rename_doc",
			"frappe.db.bulk_insert",
			"frappe.db.bulk_update",
			"frappe.db.delete",
			"frappe.db.set_value",
			"frappe.db.sql",
		}
	)
	violations: list[str] = []

	def attribute_path(node: ast.AST) -> str | None:
		parts: list[str] = []
		while isinstance(node, ast.Attribute):
			parts.append(node.attr)
			node = node.value
		if not isinstance(node, ast.Name):
			return None
		return ".".join((node.id, *reversed(parts)))

	for path in app_root.rglob("*.py"):
		if path == allowed_path or "tests" in path.parts:
			continue
		try:
			tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		except SyntaxError:
			continue
		for node in ast.walk(tree):
			if not isinstance(node, ast.Call) or attribute_path(node.func) not in forbidden_calls:
				continue
			literals = [
				constant.value
				for constant in ast.walk(node)
				if isinstance(constant, ast.Constant) and isinstance(constant.value, str)
			]
			if any(ledger_pattern.fullmatch(value) or f"tab{value}" in value for value in literals):
				violations.append(
					f"{path.relative_to(root)}:{node.lineno} bypasses the immutable-ledger service"
				)
	return violations


def validate_immutable_ledger_contract(root: Path) -> list[str]:
	common_path = root / APP_NAME / "common" / "immutable_ledger.py"
	service_path = root / APP_NAME / "services" / "immutable_ledger.py"
	api_path = root / APP_NAME / "api" / "v1" / "ledgers.py"
	documentation_path = root / "architecture" / "immutable_ledgers.md"
	adr_path = root / "architecture" / "adr" / "ADR-0007-immutable-ledger-base.md"
	task_path = root / "backlog" / "COD-012.md"
	change_path = root / "changes" / "COD-012.json"
	test_paths = (
		root / "tests" / "test_immutable_ledger.py",
		root / APP_NAME / "hrp_foundation" / "tests" / "test_immutable_ledger.py",
	)
	blueprint_paths = (
		root / "doctype_blueprints" / "hrp_budget" / "hrp_budget_ledger.json",
		root / "doctype_blueprints" / "hrp_inventory_spd" / "hrp_department_stock_ledger.json",
	)
	catalog_paths = (
		root / "api" / "api_catalog.csv",
		root / "api" / "api_catalog.yaml",
		root / "api" / "openapi.yaml",
	)
	required_paths = (
		common_path,
		service_path,
		api_path,
		documentation_path,
		adr_path,
		task_path,
		change_path,
		*test_paths,
		*blueprint_paths,
		*catalog_paths,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.is_file()]
	if missing:
		return [f"missing immutable ledger contract file: {path}" for path in missing]

	violations = find_direct_immutable_ledger_bypasses(root)
	common_text = common_path.read_text(encoding="utf-8")
	for token in (
		"class ImmutableLedgerDefinition",
		"BASE_LEDGER_FIELDS",
		"build_reversal_values",
		"assert_reversal_matches",
		"one_reversal_per_entry",
		'"http_write_enabled": False',
	):
		if token not in common_text:
			violations.append(f"immutable ledger model is missing: {token}")

	service_text = service_path.read_text(encoding="utf-8")
	for token in (
		"class ImmutableLedgerDocument",
		"class AppendImmutableLedgerService",
		"class ReverseImmutableLedgerService",
		"for_update=True",
		"wait=False",
		"immutable_ledger_appended",
		"immutable_ledger_reversed",
		'raise_ione_error("OPERATION_NOT_ALLOWED")',
	):
		if token not in service_text:
			violations.append(f"immutable ledger service is missing: {token}")
	if "frappe.db.commit" in service_text:
		violations.append("immutable ledger service must not own the transaction commit")

	expected_fields = {field.fieldname: (field.fieldtype, field.required) for field in BASE_LEDGER_FIELDS}
	for blueprint_path in blueprint_paths:
		payload = json.loads(blueprint_path.read_text(encoding="utf-8"))
		fields = {
			str(field.get("fieldname")): field
			for field in payload.get("fields", [])
			if isinstance(field, dict)
		}
		for fieldname, (fieldtype, required) in expected_fields.items():
			field = fields.get(fieldname)
			if field is None or field.get("fieldtype") != fieldtype or (required and field.get("reqd") != 1):
				violations.append(
					f"{blueprint_path.relative_to(root)} violates base ledger field {fieldname}"
				)
		if payload.get("is_submittable") != 0 or payload.get("allow_rename") != 0:
			violations.append(f"{blueprint_path.relative_to(root)} must be append-only")
		for permission in payload.get("permissions", []):
			if any(
				bool(permission.get(permission_name))
				for permission_name in IMMUTABLE_LEDGER_FORBIDDEN_PERMISSIONS
				if permission_name in permission
			):
				violations.append(f"{blueprint_path.relative_to(root)} contains a ledger write permission")

	ledger_api = "/api/method/ione_hrp.api.v1.ledgers.get_immutable_ledger_contract"
	for catalog_path in catalog_paths:
		if ledger_api not in catalog_path.read_text(encoding="utf-8"):
			violations.append(f"{catalog_path.relative_to(root)} is missing the immutable ledger endpoint")
	openapi = yaml.safe_load((root / "api" / "openapi.yaml").read_text(encoding="utf-8"))
	operation = openapi.get("paths", {}).get(ledger_api, {}).get("get", {})
	if operation.get("x-transaction-boundary") != "Read-only":
		violations.append("PLT-015 immutable ledger contract API must be read-only")
	if operation.get("x-required-role") != "System Manager or HRP System Manager":
		violations.append("PLT-015 immutable ledger contract API has the wrong role contract")
	return violations


def find_direct_transactional_message_bypasses(root: Path) -> list[str]:
	"""Keep concrete HRP Outbox and Inbox access behind the shared message service."""
	app_root = root / APP_NAME
	allowed_path = app_root / "services" / "transactional_message.py"
	message_pattern = re.compile(r"^HRP [A-Za-z0-9][A-Za-z0-9 -]{1,126} (?:Outbox|Inbox)$")
	forbidden_calls = frozenset(
		{
			"frappe.delete_doc",
			"frappe.get_doc",
			"frappe.new_doc",
			"frappe.rename_doc",
			"frappe.db.bulk_insert",
			"frappe.db.bulk_update",
			"frappe.db.delete",
			"frappe.db.set_value",
			"frappe.db.sql",
		}
	)
	violations: list[str] = []

	def attribute_path(node: ast.AST) -> str | None:
		parts: list[str] = []
		while isinstance(node, ast.Attribute):
			parts.append(node.attr)
			node = node.value
		if not isinstance(node, ast.Name):
			return None
		return ".".join((node.id, *reversed(parts)))

	if not app_root.is_dir():
		return [f"missing {APP_NAME} package directory"]
	for path in app_root.rglob("*.py"):
		if path == allowed_path or "tests" in path.parts:
			continue
		try:
			tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		except SyntaxError:
			continue
		for node in ast.walk(tree):
			if not isinstance(node, ast.Call) or attribute_path(node.func) not in forbidden_calls:
				continue
			literals = [
				constant.value
				for constant in ast.walk(node)
				if isinstance(constant, ast.Constant) and isinstance(constant.value, str)
			]
			if any(message_pattern.fullmatch(value) or f"tab{value}" in value for value in literals):
				violations.append(
					f"{path.relative_to(root)}:{node.lineno} bypasses the transactional-message service"
				)
	return violations


def validate_transactional_message_contract(root: Path) -> list[str]:
	common_path = root / APP_NAME / "common" / "transactional_message.py"
	service_path = root / APP_NAME / "services" / "transactional_message.py"
	api_path = root / APP_NAME / "api" / "v1" / "messages.py"
	documentation_path = root / "architecture" / "transactional_messages.md"
	adr_path = root / "architecture" / "adr" / "ADR-0008-transactional-outbox-inbox.md"
	task_path = root / "backlog" / "COD-013.md"
	change_path = root / "changes" / "COD-013.json"
	test_paths = (
		root / "tests" / "test_transactional_message.py",
		root / APP_NAME / "hrp_integration" / "tests" / "test_transactional_message.py",
	)
	catalog_paths = (
		root / "api" / "api_catalog.csv",
		root / "api" / "api_catalog.yaml",
		root / "api" / "openapi.yaml",
	)
	required_paths = (
		common_path,
		service_path,
		api_path,
		documentation_path,
		adr_path,
		task_path,
		change_path,
		*test_paths,
		*catalog_paths,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.is_file()]
	if missing:
		return [f"missing transactional message contract file: {path}" for path in missing]

	violations = find_direct_transactional_message_bypasses(root)
	common_text = common_path.read_text(encoding="utf-8")
	for token in (
		"class MessageBoxDefinition",
		"BASE_MESSAGE_FIELDS",
		"normalize_message_snapshot",
		"message_record_name",
		"processing_token_matches",
		'"outbox_delivery": "at_least_once"',
		'"inbox_deduplication": "consumer_and_event_id"',
		'"http_write_enabled": False',
	):
		if token not in common_text:
			violations.append(f"transactional message model is missing: {token}")
	if len(BASE_MESSAGE_FIELDS) != 23:
		violations.append("transactional message base must define exactly 23 fields")

	service_text = service_path.read_text(encoding="utf-8")
	for token in (
		"class TransactionalMessageDocument",
		"class PublishOutboxService",
		"class ClaimOutboxService",
		"class CompleteOutboxService",
		"class FailOutboxService",
		"class BeginInboxService",
		"class CompleteInboxService",
		"class FailInboxService",
		"for_update=True",
		"wait=False",
		"processing_token_hash",
		"transactional_outbox_published",
		"transactional_inbox_started",
		'raise_ione_error("OPERATION_NOT_ALLOWED")',
	):
		if token not in service_text:
			violations.append(f"transactional message service is missing: {token}")
	if "frappe.db.commit" in service_text:
		violations.append("transactional message service must not own the transaction commit")
	try:
		service_tree = ast.parse(service_text, filename=str(service_path))
	except SyntaxError as exc:
		violations.append(f"transactional message service is invalid Python: {exc}")
	else:
		network_roots = {"aiohttp", "httpx", "requests", "socket", "urllib"}
		imported_roots: set[str] = set()
		for node in ast.walk(service_tree):
			if isinstance(node, ast.Import):
				imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
			elif isinstance(node, ast.ImportFrom) and node.module:
				imported_roots.add(node.module.split(".", 1)[0])
		if imported_roots.intersection(network_roots):
			violations.append("transactional message base must not import a network client")

	message_api = "/api/method/ione_hrp.api.v1.messages.get_transactional_message_contract"
	for catalog_path in catalog_paths:
		if message_api not in catalog_path.read_text(encoding="utf-8"):
			violations.append(
				f"{catalog_path.relative_to(root)} is missing the transactional message endpoint"
			)
	openapi = yaml.safe_load((root / "api" / "openapi.yaml").read_text(encoding="utf-8"))
	operation = openapi.get("paths", {}).get(message_api, {}).get("get", {})
	if operation.get("x-transaction-boundary") != "Read-only":
		violations.append("PLT-016 transactional message contract API must be read-only")
	if operation.get("x-required-role") != "System Manager or HRP System Manager":
		violations.append("PLT-016 transactional message contract API has the wrong role contract")
	if "post" in openapi.get("paths", {}).get(message_api, {}):
		violations.append("PLT-016 transactional message contract must not expose writes")
	return violations


def validate_test_data_factory_contract(root: Path) -> list[str]:
	config_path = root / APP_NAME / "config" / "test_data_scenarios.json"
	common_path = root / APP_NAME / "common" / "test_data_factory.py"
	service_path = root / APP_NAME / "services" / "test_data_factory.py"
	facade_path = root / APP_NAME / "hrp_foundation" / "services" / "test_data.py"
	api_path = root / APP_NAME / "api" / "v1" / "test_data.py"
	documentation_path = root / "architecture" / "test_data_factory.md"
	adr_path = root / "architecture" / "adr" / "ADR-0009-source-controlled-test-data-factory.md"
	task_path = root / "backlog" / "COD-014.md"
	change_path = root / "changes" / "COD-014.json"
	test_paths = (
		root / "tests" / "test_test_data_factory.py",
		root / APP_NAME / "hrp_foundation" / "tests" / "test_test_data_factory.py",
	)
	catalog_paths = (
		root / "api" / "api_catalog.csv",
		root / "api" / "api_catalog.yaml",
		root / "api" / "openapi.yaml",
	)
	required_paths = (
		config_path,
		common_path,
		service_path,
		facade_path,
		api_path,
		documentation_path,
		adr_path,
		task_path,
		change_path,
		*test_paths,
		*catalog_paths,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.is_file()]
	if missing:
		return [f"missing test data factory contract file: {path}" for path in missing]

	violations: list[str] = []
	try:
		registry = load_test_data_scenario_registry(config_path)
	except TestDataFactoryContractError as exc:
		return [f"invalid test data scenario registry: {exc}"]
	if not registry.scenarios:
		violations.append("test data factory must declare at least one source-controlled scenario")
	for scenario in registry.scenarios:
		if set(scenario.allowed_profiles) - {"development", "test"}:
			violations.append(f"{scenario.scenario_id} permits a non-test environment")
		if scenario.contains_personal_data:
			violations.append(f"{scenario.scenario_id} permits personal data")
		scenario.ordered_steps()

	common_text = common_path.read_text(encoding="utf-8")
	for token in (
		"class TestDataScenarioDefinition",
		"class TestDataScenarioRegistry",
		"ordered_steps",
		"normalize_test_data_seed",
		"test_dataset_id",
		"synthetic_identifier",
		'"arbitrary_doctype_input": False',
		'"contains_personal_data": False',
		'"http_write_enabled": False',
	):
		if token not in common_text:
			violations.append(f"test data factory model is missing: {token}")

	service_text = service_path.read_text(encoding="utf-8")
	for token in (
		"class GenerateTestDataService",
		"DomainServiceDefinition",
		"require_roles",
		"_assert_generation_allowed",
		"synthetic_data_only",
		"allow_tests",
		"_STEP_BUILDERS",
		"document.insert(ignore_permissions=True)",
		"test_data_factory_generated",
	):
		if token not in service_text:
			violations.append(f"test data factory service is missing: {token}")
	if "frappe.db.commit" in service_text:
		violations.append("test data factory service must not own the transaction commit")
	if "GL Entry" in service_text or "Stock Ledger Entry" in service_text or '"Bin"' in service_text:
		violations.append("test data factory must not write protected ERPNext ledgers")
	if "importlib" in common_text or "importlib" in service_text:
		violations.append("test data factory builders must not use dynamic imports")

	api_text = api_path.read_text(encoding="utf-8")
	if '@frappe.whitelist(allow_guest=True, methods=["GET"])' not in api_text:
		violations.append("PLT-017 test data factory contract must be GET-only")
	if "generate_test_data" in api_text:
		violations.append("test data generation must not be exposed through HTTP")

	factory_api = "/api/method/ione_hrp.api.v1.test_data.get_test_data_factory_contract"
	for catalog_path in catalog_paths:
		if factory_api not in catalog_path.read_text(encoding="utf-8"):
			violations.append(f"{catalog_path.relative_to(root)} is missing the test data factory endpoint")
	openapi = yaml.safe_load((root / "api" / "openapi.yaml").read_text(encoding="utf-8"))
	path_contract = openapi.get("paths", {}).get(factory_api, {})
	operation = path_contract.get("get", {})
	if operation.get("x-transaction-boundary") != "Read-only":
		violations.append("PLT-017 test data factory contract API must be read-only")
	if operation.get("x-required-role") != "System Manager or HRP System Manager":
		violations.append("PLT-017 test data factory contract API has the wrong role contract")
	if set(path_contract) != {"get"}:
		violations.append("PLT-017 test data factory contract must not expose writes")
	return violations


def validate_environment_profiles(root: Path) -> list[str]:
	profile_path = root / APP_NAME / "config" / "environment_profiles.json"
	manager_path = root / "scripts" / "environment_manager.py"
	integration_path = root / "scripts" / "ci_integration.sh"
	api_catalog_path = root / "api" / "api_catalog.csv"
	openapi_path = root / "api" / "openapi.yaml"
	required_paths = (
		profile_path,
		manager_path,
		integration_path,
		api_catalog_path,
		openapi_path,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.is_file()]
	if missing:
		return [f"missing environment delivery file: {path}" for path in missing]

	violations: list[str] = []
	try:
		registry = load_environment_registry(profile_path)
	except EnvironmentProfileError as exc:
		return [f"invalid environment profiles: {exc}"]
	if tuple(profile.name for profile in registry.profiles) != ("development", "test", "demo"):
		violations.append("environment profiles must be development, test and demo")

	manager_text = manager_path.read_text(encoding="utf-8")
	for token in (
		"bootstrap_latest_develop.sh",
		"version_lock.py",
		"list-apps",
		"migrate",
		"environment-audit.jsonl",
		"DB_ROOT_PASSWORD",
		"ADMIN_PASSWORD",
		"--allow-target-override",
	):
		if token not in manager_text:
			violations.append(f"environment manager is missing: {token}")

	integration_text = integration_path.read_text(encoding="utf-8")
	for token in (
		"environment_manager.py",
		"configure test",
		"verify test",
		'"changed": false',
	):
		if token not in integration_text:
			violations.append(f"CI does not validate environment profiles: {token}")

	environment_api = "/api/method/ione_hrp.api.v1.environment.get_environment_status"
	if environment_api not in api_catalog_path.read_text(encoding="utf-8"):
		violations.append("API catalog is missing the environment status endpoint")
	if environment_api not in openapi_path.read_text(encoding="utf-8"):
		violations.append("OpenAPI is missing the environment status endpoint")
	return violations


def validate_fixture_governance(root: Path) -> list[str]:
	policy_path = root / APP_NAME / "config" / "fixture_policy.json"
	modules_path = root / APP_NAME / "modules.txt"
	fixture_directory = root / APP_NAME / "fixtures"
	hooks_path = root / APP_NAME / "hooks.py"
	manager_path = root / "scripts" / "fixture_manager.py"
	integration_path = root / "scripts" / "ci_integration.sh"
	documentation_path = root / "architecture" / "fixtures.md"
	api_catalog_path = root / "api" / "api_catalog.csv"
	openapi_path = root / "api" / "openapi.yaml"
	required_paths = (
		policy_path,
		modules_path,
		fixture_directory,
		hooks_path,
		manager_path,
		integration_path,
		documentation_path,
		api_catalog_path,
		openapi_path,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.exists()]
	if missing:
		return [f"missing fixture governance file: {path}" for path in missing]

	violations: list[str] = []
	try:
		policy = load_fixture_policy(policy_path, modules_path=modules_path)
		report = inspect_fixture_repository(policy, fixture_directory)
	except FixturePolicyError as exc:
		return [f"invalid fixture governance: {exc}"]
	if tuple(rule.doctype for rule in policy.rules) != (
		"Custom Field",
		"Property Setter",
		"Custom DocPerm",
	):
		violations.append("fixture allowlist must contain only the approved configuration DocTypes")
	if report.files != 3:
		violations.append("fixture repository must contain all three ordered files")

	hooks_text = hooks_path.read_text(encoding="utf-8")
	for token in (
		"get_frappe_fixture_hooks",
		"fixture_auto_order = True",
		"fixtures = get_frappe_fixture_hooks()",
	):
		if token not in hooks_text:
			violations.append(f"hooks.py is missing fixture governance token: {token}")

	manager_text = manager_path.read_text(encoding="utf-8")
	for token in (
		"export-fixtures",
		"assert_fixture_export_allowed",
		"fixture-export-audit.jsonl",
		"--yes",
		"Repeated fixture export is not idempotent",
	):
		if token not in manager_text:
			violations.append(f"fixture manager is missing: {token}")

	integration_text = integration_path.read_text(encoding="utf-8")
	for token in (
		"fixture_manager.py",
		"COD-007",
		"fixture-export-audit.jsonl",
	):
		if token not in integration_text:
			violations.append(f"CI does not validate fixture governance: {token}")

	fixture_api = "/api/method/ione_hrp.api.v1.fixtures.get_fixture_governance_status"
	if fixture_api not in api_catalog_path.read_text(encoding="utf-8"):
		violations.append("API catalog is missing the fixture governance endpoint")
	if fixture_api not in openapi_path.read_text(encoding="utf-8"):
		violations.append("OpenAPI is missing the fixture governance endpoint")
	return violations


def validate_change_governance(root: Path) -> list[str]:
	policy_path = root / APP_NAME / "config" / "change_governance.json"
	manager_path = root / "scripts" / "change_manager.py"
	documentation_path = root / "architecture" / "change_governance.md"
	template_path = root / "architecture" / "ADR_TEMPLATE.md"
	adr_directory = root / "architecture" / "adr"
	change_directory = root / "changes"
	task_path = root / "backlog" / "COD-008.md"
	pr_template_path = root / ".github" / "pull_request_template.md"
	workflow_path = root / ".github" / "workflows" / "ci.yml"
	catalog_paths = (
		root / "api" / "api_catalog.csv",
		root / "api" / "api_catalog.yaml",
		root / "api" / "openapi.yaml",
	)
	required_paths = (
		policy_path,
		manager_path,
		documentation_path,
		template_path,
		adr_directory,
		change_directory,
		task_path,
		pr_template_path,
		workflow_path,
		*catalog_paths,
	)
	missing = [str(path.relative_to(root)) for path in required_paths if not path.exists()]
	if missing:
		return [f"missing change governance file: {path}" for path in missing]

	try:
		report = inspect_change_governance(root)
	except ChangeGovernanceError as exc:
		return [f"invalid change governance: {exc}"]
	violations: list[str] = []
	if report.policy.baseline_task_id != "COD-008":
		violations.append("change governance baseline task must be COD-008")
	if len(report.decisions) < 2:
		violations.append("change governance must include the baseline architecture decisions")
	if len(report.changes) < 8:
		violations.append("change governance must backfill completed COD-001 through COD-007")
	if "COD-008" not in report.change_by_task:
		violations.append("change governance must include COD-008")

	manager_text = manager_path.read_text(encoding="utf-8")
	for token in (
		"inspect_change_governance",
		"assess_changed_paths",
		"validate_adr_transition",
		"merge-base",
		"ione_hrp-change-governance-audit.jsonl",
		"production_write_enabled",
		"http_write_enabled",
	):
		if token not in manager_text:
			violations.append(f"change manager is missing: {token}")

	workflow_text = workflow_path.read_text(encoding="utf-8")
	for token in (
		"CHANGE_BASE",
		"python scripts/change_manager.py check",
		"python scripts/change_manager.py validate",
	):
		if token not in workflow_text:
			violations.append(f"CI does not enforce change governance: {token}")

	pr_template_text = pr_template_path.read_text(encoding="utf-8")
	for token in ("ADR 编号", "变更记录", "破坏性变更", "change_manager.py"):
		if token not in pr_template_text:
			violations.append(f"PR template is missing change governance evidence: {token}")

	governance_api = "/api/method/ione_hrp.api.v1.change_governance.get_change_governance_status"
	for catalog_path in catalog_paths:
		if governance_api not in catalog_path.read_text(encoding="utf-8"):
			violations.append(f"{catalog_path.relative_to(root)} is missing the change governance endpoint")
	return violations


def collect_violations(root: Path) -> list[str]:
	root = root.resolve()
	violations: list[str] = []
	apps = discover_custom_apps(root)
	if set(apps) != {APP_NAME}:
		violations.append(f"repository must contain exactly {APP_NAME}; found {sorted(apps)}")
	apps_root = root / "apps"
	if any((apps_root / upstream).exists() for upstream in UPSTREAM_APPS):
		violations.append("upstream Frappe/ERPNext/HRMS source must not be vendored or modified")
	if apps_root.is_dir() and any(
		path.name.startswith(f"{APP_NAME}_") for path in apps_root.iterdir() if path.is_dir()
	):
		violations.append("business domains must be modules, not additional ione_hrp_* apps")

	app_root = root
	package_root = root / APP_NAME
	if not (package_root / "__init__.py").is_file():
		violations.append("missing ione_hrp Python package")
	elif apps.get(APP_NAME) != app_root:
		violations.append("ione_hrp pyproject must be at repository root for Press")
	if not (package_root / "hooks.py").is_file():
		violations.append("missing Press-discoverable ione_hrp/hooks.py")

	violations.extend(find_legacy_prefix_references(root))
	violations.extend(validate_branch_policy(root))
	violations.extend(validate_push_guard(root))
	violations.extend(validate_quality_tooling(root))
	violations.extend(validate_ci_pipeline(root))
	violations.extend(validate_version_baseline(root))
	violations.extend(validate_catalog_ownership(root))
	violations.extend(validate_module_structure(root))
	violations.extend(validate_module_boundaries(root))
	violations.extend(validate_protected_ledgers(root))
	violations.extend(validate_environment_profiles(root))
	violations.extend(validate_fixture_governance(root))
	violations.extend(validate_change_governance(root))
	violations.extend(validate_error_contract(root))
	violations.extend(validate_audit_context_contract(root))
	violations.extend(validate_domain_service_contract(root))
	violations.extend(validate_immutable_ledger_contract(root))
	violations.extend(validate_transactional_message_contract(root))
	violations.extend(validate_test_data_factory_contract(root))
	return violations


def main() -> int:
	root = Path(__file__).resolve().parents[1]
	violations = collect_violations(root)
	if violations:
		print("REPOSITORY CONTRACT FAILED", file=sys.stderr)
		for violation in violations:
			print(f"- {violation}", file=sys.stderr)
		return 1
	print(
		json.dumps(
			{
				"status": "ok",
				"custom_app": APP_NAME,
				"modules": 36,
				"protected_branch": "main",
				"pull_requests": "required",
			},
			ensure_ascii=False,
		)
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
