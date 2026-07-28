#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_DIR="${BENCH_DIR:-$HOME/frappe-bench-hrp}"
SITE_NAME="${SITE_NAME:-hrp.localhost}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-develop}"
ERPNEXT_BRANCH="${ERPNEXT_BRANCH:-develop}"
HRMS_BRANCH="${HRMS_BRANCH:-develop}"
PYTHON_BIN="${PYTHON_BIN:-python3.10}"
DB_TYPE="${DB_TYPE:-mariadb}"
DB_ROOT_USERNAME="${DB_ROOT_USERNAME:-root}"
DEVELOPER_MODE="${DEVELOPER_MODE:-1}"

: "${DB_ROOT_PASSWORD:?Set DB_ROOT_PASSWORD in the environment or .env}"
: "${ADMIN_PASSWORD:?Set ADMIN_PASSWORD in the environment or .env}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first, then rerun." >&2
  exit 1
fi

uv tool install frappe-bench --force

if [[ -e "$BENCH_DIR" ]]; then
  echo "Bench directory already exists: $BENCH_DIR" >&2
  exit 1
fi

bench init "$BENCH_DIR" \
  --frappe-path https://github.com/frappe/frappe.git \
  --frappe-branch "$FRAPPE_BRANCH" \
  --python "$PYTHON_BIN" \
  --dev

cd "$BENCH_DIR"
bench get-app --branch "$ERPNEXT_BRANCH" erpnext https://github.com/frappe/erpnext.git
bench get-app --branch "$HRMS_BRANCH" hrms https://github.com/frappe/hrms.git

git clone --no-hardlinks "$ROOT_DIR" "$BENCH_DIR/apps/ione_hrp"
./env/bin/python -m pip install -e apps/ione_hrp
if ! grep -qxF ione_hrp sites/apps.txt; then
  echo ione_hrp >> sites/apps.txt
fi

bench new-site "$SITE_NAME" \
  --db-type "$DB_TYPE" \
  --db-root-username "$DB_ROOT_USERNAME" \
  --db-root-password "$DB_ROOT_PASSWORD" \
  --admin-password "$ADMIN_PASSWORD" \
  --set-default

bench --site "$SITE_NAME" install-app erpnext
bench --site "$SITE_NAME" install-app hrms
bench --site "$SITE_NAME" install-app ione_hrp
bench set-config -g developer_mode "$DEVELOPER_MODE"
bench --site "$SITE_NAME" migrate
bench build --app ione_hrp

"$ROOT_DIR/scripts/lock_versions.sh" "$BENCH_DIR" "$ROOT_DIR/resolved_versions.lock.json"
echo "Ready. Run: cd '$BENCH_DIR' && bench start"
