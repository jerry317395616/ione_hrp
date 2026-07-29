from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

DOMAIN_GROUPS = (
    "Core",
    "Finance",
    "Supply",
    "Asset",
    "People",
    "Project",
    "Governance",
    "Platform",
    "Portal",
    "Other",
)


def scrub_module_package(name: str) -> str:
    value = name.strip().lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    if not value.startswith("hrp_"):
        value = "hrp_" + value.removeprefix("hrp_")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError(f"Invalid module package: {value}")
    return value


def _validated_text(value: str, field: str, *, max_length: int) -> str:
    result = value.strip()
    if not result:
        raise ValueError(f"{field} is required")
    if any(char in result for char in ("\\r", "\\n", "\\x00")):
        raise ValueError(f"{field} must be one line")
    if len(result) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    return result


def create_module_files(
    *,
    name: str,
    domain_group: str,
    label_cn: str,
    description: str,
    app_root: Path | None = None,
) -> dict[str, Any]:
    """Create a version-controlled Frappe module inside the ione_hrp app.

    This intentionally edits source files and is therefore a developer operation, not a
    production Desk action. The caller must review and commit the generated files.
    """
    name = _validated_text(name, "name", max_length=140)
    domain_group = _validated_text(domain_group, "domain_group", max_length=40)
    label_cn = _validated_text(label_cn, "label_cn", max_length=140)
    description = _validated_text(description, "description", max_length=500)
    if not name.startswith("HRP "):
        raise ValueError("Module display name must start with 'HRP '")
    if domain_group not in DOMAIN_GROUPS:
        raise ValueError(f"domain_group must be one of: {', '.join(DOMAIN_GROUPS)}")

    app_root = (app_root or Path(__file__).resolve().parents[2]).resolve()
    package_root = app_root / "ione_hrp"
    modules_file = package_root / "modules.txt"
    registry_file = app_root / "architecture" / "module_registry.yaml"
    if not modules_file.is_file() or not registry_file.is_file():
        raise FileNotFoundError("ione_hrp source tree is incomplete")

    package = scrub_module_package(name)
    module_root = package_root / package
    modules = [line.strip() for line in modules_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    registry = yaml.safe_load(registry_file.read_text(encoding="utf-8")) or {}
    rows = registry.setdefault("modules", [])

    if name in modules or any(row.get("module") == name for row in rows):
        raise FileExistsError(f"Module display name already exists: {name}")
    if module_root.exists() or any(row.get("package") == package for row in rows):
        raise FileExistsError(f"Module package already exists: {package}")

    for subpackage in ("doctype", "report", "page", "workspace", "services", "api", "tests"):
        path = module_root / subpackage
        path.mkdir(parents=True, exist_ok=False)
        (path / "__init__.py").write_text("", encoding="utf-8")
    (module_root / "__init__.py").write_text(f'"""{name}."""\\n', encoding="utf-8")
    (module_root / "README.md").write_text(
        f"# {name}\\n\\n**领域组：** {domain_group}\\n\\n"
        f"**中文名称：** {label_cn}\\n\\n{description}\\n",
        encoding="utf-8",
    )

    modules_file.write_text("\\n".join([*modules, name]) + "\\n", encoding="utf-8")
    rows.append(
        {
            "sequence": max([int(row.get("sequence", 0)) for row in rows] or [0]) + 10,
            "module": name,
            "package": package,
            "domain_group": domain_group,
            "label_cn": label_cn,
            "enabled_by_default": True,
            "description": description,
        }
    )
    registry["module_count"] = len(rows)
    registry_file.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    return {
        "module": name,
        "package": package,
        "domain_group": domain_group,
        "module_root": str(module_root),
        "module_count": len(rows),
    }
