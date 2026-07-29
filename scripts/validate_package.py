from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import tomllib
import yaml
from version_lock import load_lock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ione_hrp.services.module_registry import (
    load_module_registry,
    validate_module_source_tree,
)

APP = ROOT
PKG = ROOT / "ione_hrp"


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    pyproject = tomllib.loads((APP / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject["project"]["name"] != "ione_hrp":
        fail("pyproject project name mismatch")
    load_lock(ROOT / "resolved_versions.lock.json")

    registry = load_module_registry(ROOT)
    module_violations = validate_module_source_tree(ROOT, expected_module_count=36)
    if module_violations:
        fail("; ".join(module_violations))

    for json_file in PKG.rglob("*.json"):
        json.loads(json_file.read_text(encoding="utf-8"))
    for yaml_file in ROOT.rglob("*.yaml"):
        yaml.safe_load(yaml_file.read_text(encoding="utf-8"))

    with (ROOT / "design" / "doctype_catalog.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 398:
        fail(f"expected 398 design DocTypes, got {len(rows)}")
    if {row["app"] for row in rows} != {"ione_hrp"}:
        fail("doctype catalog contains non-single-app values")

    blueprint_files = list((ROOT / "doctype_blueprints").rglob("*.json"))
    if len(blueprint_files) != 398:
        fail(f"expected 398 blueprint files, got {len(blueprint_files)}")

    print(
        json.dumps(
            {
                "status": "ok",
                "modules": len(registry.modules),
                "doctypes": len(rows),
                "blueprints": len(blueprint_files),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        raise
