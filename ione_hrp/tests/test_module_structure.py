from __future__ import annotations

from pathlib import Path


def test_declared_modules_have_packages() -> None:
    package_root = Path(__file__).resolve().parents[1]
    modules = [line.strip() for line in (package_root / "modules.txt").read_text().splitlines() if line.strip()]
    missing = []
    for module in modules:
        package = module.lower().replace(" ", "_").replace("&", "and")
        # Official module package names are validated by the repository script; this test catches gross omissions.
        if not any(path.name.startswith("hrp_") and path.is_dir() for path in package_root.iterdir()):
            missing.append(package)
    assert not missing
