from __future__ import annotations

import ast
import csv
import json
import re
import sys
from pathlib import Path

import tomllib

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
	sys.path.insert(0, str(REPOSITORY_ROOT))

from ione_hrp.services.module_registry import validate_module_source_tree

if __package__:
	from scripts.version_lock import UPSTREAM_APPS, load_lock
else:
	from version_lock import UPSTREAM_APPS, load_lock

APP_NAME = "ione_hrp"
UPSTREAM_APPS = frozenset({"frappe", "erpnext", "hrms"})
LEGACY_PREFIXES = ("myi" + "_hrp", "myi" + "-hrp")
PROTECTED_LEDGER_PATTERNS = (
	re.compile(r"""(?:new_doc|get_doc)\(\s*["']GL Entry["']"""),
	re.compile(r"""(?:new_doc|get_doc)\(\s*["']Stock Ledger Entry["']"""),
	re.compile(r"""(?:new_doc|get_doc)\(\s*["']Bin["']"""),
	re.compile(r"""tab(?:GL Entry|Stock Ledger Entry|Bin)"""),
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
	if not any(re.fullmatch(r"ruff==\d+\.\d+\.\d+(?:[-.][0-9A-Za-z]+)*", item) for item in dev_extras):
		violations.append("Ruff must be pinned exactly in project.optional-dependencies.dev")
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
	violations.extend(validate_version_baseline(root))
	violations.extend(validate_catalog_ownership(root))
	violations.extend(validate_module_structure(root))
	violations.extend(validate_module_boundaries(root))
	violations.extend(validate_protected_ledgers(root))
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
