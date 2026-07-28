from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


def scrub(name: str) -> str:
    value = name.strip().lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    if not value.startswith("hrp_"):
        value = "hrp_" + value.removeprefix("hrp_")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError(f"Invalid module package: {value}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new module inside the single ione_hrp app")
    parser.add_argument("--name", required=True, help='Display name, e.g. "HRP Medical Insurance"')
    parser.add_argument("--group", required=True)
    parser.add_argument("--label-cn", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    app_package = root / "ione_hrp"
    modules_file = app_package / "modules.txt"
    registry_file = root / "architecture" / "module_registry.yaml"

    name = args.name.strip()
    if not name.startswith("HRP "):
        raise SystemExit("Module display name must start with 'HRP '")
    package = scrub(name)
    modules = [line.strip() for line in modules_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if name in modules or (app_package / package).exists():
        raise SystemExit(f"Module already exists: {name} / {package}")

    module_root = app_package / package
    for sub in ["doctype", "report", "page", "workspace", "services", "api", "tests"]:
        path = module_root / sub
        path.mkdir(parents=True, exist_ok=True)
        (path / "__init__.py").write_text("", encoding="utf-8")
    (module_root / "__init__.py").write_text(f'"""{name}."""\n', encoding="utf-8")
    (module_root / "README.md").write_text(
        f"# {name}\n\n**领域组：** {args.group}\n\n**中文名称：** {args.label_cn}\n\n{args.description}\n",
        encoding="utf-8",
    )
    modules_file.write_text("\n".join([*modules, name]) + "\n", encoding="utf-8")

    registry = yaml.safe_load(registry_file.read_text(encoding="utf-8")) or {}
    rows = registry.setdefault("modules", [])
    rows.append(
        {
            "sequence": max([int(row.get("sequence", 0)) for row in rows] or [0]) + 10,
            "module": name,
            "package": package,
            "domain_group": args.group,
            "label_cn": args.label_cn,
            "enabled_by_default": True,
            "description": args.description,
        }
    )
    registry["module_count"] = len(rows)
    registry_file.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Created {name} at {module_root}")
    print("Next: review files, add DocTypes, then run bench --site <site> migrate")


if __name__ == "__main__":
    main()
