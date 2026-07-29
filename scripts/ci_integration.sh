#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_DIR="${BENCH_DIR:?Set BENCH_DIR to an empty CI workspace path}"
SITE_NAME="${SITE_NAME:-test_site}"
REDIS_CACHE_PORT="${REDIS_CACHE_PORT:-13000}"
REDIS_QUEUE_PORT="${REDIS_QUEUE_PORT:-11000}"

if [[ -e "$BENCH_DIR" ]]; then
  echo "CI Bench directory already exists: $BENCH_DIR" >&2
  exit 1
fi

export PATH="$HOME/.local/bin:$PATH"

stop_redis() {
  redis-cli -p "$REDIS_CACHE_PORT" shutdown nosave >/dev/null 2>&1 || true
  redis-cli -p "$REDIS_QUEUE_PORT" shutdown nosave >/dev/null 2>&1 || true
}

trap stop_redis EXIT

export KEEP_TEMPORARY_REDIS=1
bash "$ROOT_DIR/scripts/bootstrap_latest_develop.sh"

for port in "$REDIS_CACHE_PORT" "$REDIS_QUEUE_PORT"; do
  if [[ "$(redis-cli -p "$port" ping)" != "PONG" ]]; then
    echo "CI Redis service on port $port is not ready" >&2
    exit 1
  fi
done

cd "$BENCH_DIR"

"$BENCH_DIR/env/bin/python" "$ROOT_DIR/scripts/version_lock.py" --bench "$BENCH_DIR"
bench --site "$SITE_NAME" migrate --skip-search-index
bench --site "$SITE_NAME" run-tests --app ione_hrp

"$BENCH_DIR/env/bin/python" - "$BENCH_DIR" "$SITE_NAME" <<'PY'
import json
import sys
from pathlib import Path

import frappe

bench_dir = Path(sys.argv[1]).resolve()
site_name = sys.argv[2]
frappe.init(site=site_name, sites_path=str(bench_dir / "sites"))
frappe.connect()
try:
	error_log_count = frappe.db.count("Error Log")
	print(json.dumps({"site": site_name, "error_log_count": error_log_count}))
	if error_log_count:
		raise SystemExit("Fresh CI site contains Error Log records")
finally:
	frappe.destroy()
PY

for app in frappe erpnext hrms ione_hrp; do
  if [[ -n "$(git -C "$BENCH_DIR/apps/$app" status --porcelain)" ]]; then
    echo "CI validation changed the $app worktree" >&2
    git -C "$BENCH_DIR/apps/$app" status --short >&2
    exit 1
  fi
done

echo "CI integration validation passed"
