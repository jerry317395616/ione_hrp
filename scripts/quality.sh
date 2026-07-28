#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT_DIR/scripts/validate_package.py"
python3 -m compileall -q "$ROOT_DIR/ione_hrp"
if command -v ruff >/dev/null 2>&1; then
  ruff check "$ROOT_DIR/ione_hrp"
  ruff format --check "$ROOT_DIR/ione_hrp"
fi
