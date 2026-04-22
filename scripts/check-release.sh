#!/usr/bin/env bash
# =============================================================================
# Project Filum — Pre-Release Verification Script
# Usage: bash scripts/check-release.sh
# Run from the repository root.
#
# Exit codes:
#   0  All P0 checks passed — ready to release.
#   1  One or more P0 checks failed — do NOT release.
# =============================================================================

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

pass=0
fail=0
warn=0

_green="\033[0;32m"
_red="\033[0;31m"
_yellow="\033[0;33m"
_reset="\033[0m"

section() { echo; echo "── $1 ──────────────────────────────────────────"; }

check() {
  local label="$1"; shift
  printf "  %-55s" "→ $label"
  local out
  if out=$("$@" 2>&1); then
    echo -e "${_green}PASS${_reset}"
    pass=$((pass + 1))
  else
    echo -e "${_red}FAIL${_reset}"
    echo "$out" | sed 's/^/      /'
    fail=$((fail + 1))
  fi
}

check_env() {
  local var="$1"
  local default_bad="$2"
  printf "  %-55s" "→ env: $var"
  local value="${!var:-}"
  if [ -z "$value" ]; then
    echo -e "${_red}FAIL (not set)${_reset}"
    fail=$((fail + 1))
  elif [ "$value" = "$default_bad" ]; then
    echo -e "${_red}FAIL (still uses insecure default)${_reset}"
    fail=$((fail + 1))
  else
    echo -e "${_green}PASS${_reset}"
    pass=$((pass + 1))
  fi
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       Project Filum — Pre-Release Verification               ║"
echo "╚══════════════════════════════════════════════════════════════╝"

# =============================================================================
# Backend checks
# =============================================================================
section "Backend"
cd "$BACKEND_DIR"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

check "pytest (unit + integration)"  python -m pytest -q
check "compileall (syntax check)"    python -m compileall -q app tests

# =============================================================================
# Frontend checks
# =============================================================================
section "Frontend"
cd "$FRONTEND_DIR"

check "type-check (tsc)"             npm run type-check
check "unit tests (vitest)"          npm run test:unit -- --run
check "production build"             npm run build

# Lint is informational — failures are warnings, not blockers.
section "Frontend lint (informational)"
printf "  %-55s" "→ lint"
if npm run lint 2>&1 | tee /tmp/filum-lint-output.txt | grep -q "error"; then
  echo -e "${_yellow}WARN (lint errors found — review before release)${_reset}"
  warn=$((warn + 1))
else
  echo -e "${_green}PASS${_reset}"
fi

# =============================================================================
# Production environment checks (only when .env is present and APP_ENV=production)
# =============================================================================
cd "$BACKEND_DIR"
if [ -f ".env" ]; then
  section "Production environment (.env present)"
  # Source .env safely — only export key=value lines, skip comments.
  set -a
  # shellcheck source=/dev/null
  grep -E '^[A-Z_]+=.+' .env | grep -v '^#' | while IFS='=' read -r key _; do
    export "$key"
  done < <(grep -E '^[A-Z_][A-Z0-9_]*=.+' .env | grep -v '^#')
  set +a
  # Re-source properly for the variable checks below.
  export $(grep -E '^[A-Z_][A-Z0-9_]*=.+' .env | grep -v '^#' | xargs) 2>/dev/null || true

  check_env "JWT_SECRET_KEY"  "change-me-in-production"
  check_env "POSTGRES_DSN"    ""

  printf "  %-55s" "→ env: STORAGE_BASE_PATH exists"
  if [ -n "${STORAGE_BASE_PATH:-}" ] && [ -d "${STORAGE_BASE_PATH}" ]; then
    echo -e "${_green}PASS${_reset}"
    pass=$((pass + 1))
  else
    echo -e "${_yellow}WARN (directory ${STORAGE_BASE_PATH:-<not set>} not found — create before deploying)${_reset}"
    warn=$((warn + 1))
  fi
else
  section "Production environment"
  echo "  Skipping .env checks — no .env file found in backend/."
  echo "  (This is expected in CI; run manually on the target server.)"
fi

# =============================================================================
# Alembic migration chain check
# =============================================================================
section "Database migrations"
cd "$BACKEND_DIR"
if command -v alembic >/dev/null 2>&1; then
  check "alembic check (migration chain)"  alembic check
else
  echo "  alembic not found in PATH — skipping (activate virtualenv first)"
fi

# =============================================================================
# Summary
# =============================================================================
echo
echo "══════════════════════════════════════════════════════════════"
echo "  Passed: $pass  |  Failed: $fail  |  Warnings: $warn"
echo "──────────────────────────────────────────────────────────────"
if [ "$fail" -gt 0 ]; then
  echo -e "  Status: ${_red}✗  NOT READY — fix failures before releasing${_reset}"
  exit 1
else
  echo -e "  Status: ${_green}✓  READY — all P0 checks passed${_reset}"
  if [ "$warn" -gt 0 ]; then
    echo "  ($warn warning(s) — review before pushing to production)"
  fi
  exit 0
fi
