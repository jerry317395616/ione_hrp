#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="${LOCK_FILE:-$ROOT_DIR/resolved_versions.lock.json}"
BENCH_DIR="${BENCH_DIR:?Set BENCH_DIR}"
SITE_NAME="${SITE_NAME:?Set SITE_NAME}"

cd "$BENCH_DIR"
for app in frappe erpnext hrms; do
  [[ -d "apps/$app" ]] || { echo "Missing dependency app: $app" >&2; exit 1; }
done
"$ROOT_DIR/scripts/lock_versions.sh" "$BENCH_DIR" "$LOCK_FILE"

if [[ -e apps/ione_hrp ]]; then
  echo "apps/ione_hrp already exists; refusing to overwrite" >&2
  exit 1
fi
git clone --no-hardlinks "$ROOT_DIR" apps/ione_hrp
./env/bin/python -m pip install -e apps/ione_hrp
if ! grep -qxF ione_hrp sites/apps.txt; then
  echo ione_hrp >> sites/apps.txt
fi
bench --site "$SITE_NAME" install-app ione_hrp
bench --site "$SITE_NAME" migrate
bench build --app ione_hrp
