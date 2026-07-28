#!/usr/bin/env bash
set -euo pipefail
BENCH_DIR="${1:?bench directory required}"
OUTPUT="${2:-resolved_versions.lock.json}"
python3 - "$BENCH_DIR" "$OUTPUT" <<'PYLOCK'
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

bench = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
apps = ["frappe", "erpnext", "hrms", "ione_hrp"]
result = {"generated_at": datetime.now(timezone.utc).isoformat(), "bench": str(bench), "apps": {}}
for app in apps:
    path = bench / "apps" / app
    row = {"path": str(path)}
    if not path.exists():
        row["missing"] = True
        result["apps"][app] = row
        continue
    def run(*args):
        return subprocess.check_output(args, cwd=path, text=True, stderr=subprocess.DEVNULL).strip()
    try:
        row["commit"] = run("git", "rev-parse", "HEAD")
        row["branch"] = run("git", "rev-parse", "--abbrev-ref", "HEAD")
        row["dirty"] = bool(run("git", "status", "--porcelain"))
    except Exception:
        row["git"] = "unavailable"
    init_file = path / app / "__init__.py"
    if init_file.exists():
        import re
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)', init_file.read_text(encoding="utf-8"))
        if match:
            row["version"] = match.group(1)
    result["apps"][app] = row
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(out)
PYLOCK
