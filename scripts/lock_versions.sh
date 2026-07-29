#!/usr/bin/env bash
set -euo pipefail
BENCH_DIR="${1:?bench directory required}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="${2:-$ROOT_DIR/resolved_versions.lock.json}"

python3 "$ROOT_DIR/scripts/version_lock.py" \
  --lock "$LOCK_FILE" \
  --bench "$BENCH_DIR"
