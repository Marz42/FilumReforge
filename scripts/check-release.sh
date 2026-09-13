#!/usr/bin/env bash
# Use scripts/check_release.py directly for native Windows execution.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${FILUM_CHECK_PYTHON:-}" ]]; then
  PYTHON="$FILUM_CHECK_PYTHON"
elif [[ -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/backend/.venv/bin/python"
elif [[ -x "$ROOT_DIR/backend/.venv/Scripts/python.exe" ]]; then
  PYTHON="$ROOT_DIR/backend/.venv/Scripts/python.exe"
else
  PYTHON=python3
fi
exec "$PYTHON" "$ROOT_DIR/scripts/check_release.py" "$@"
