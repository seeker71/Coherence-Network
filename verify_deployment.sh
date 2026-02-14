#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-}"
WEB_BASE_URL="${WEB_BASE_URL:-}"

pass=0
fail=0

check() {
  local name="$1"
  local cmd="$2"
  echo "- $name"
  if bash -lc "$cmd"; then
    echo "  ✅ pass"
    pass=$((pass + 1))
  else
    echo "  ❌ fail"
    fail=$((fail + 1))
  fi
}

echo "Coherence deployment verification"
echo "==============================="

if [[ -n "$API_BASE_URL" ]]; then
  check "API health" "curl -fsS '$API_BASE_URL/api/health' >/dev/null"
  check "API ready" "curl -fsS '$API_BASE_URL/api/ready' >/dev/null"
  check "API version" "curl -fsS '$API_BASE_URL/api/version' >/dev/null"
else
  echo "⚠️  API_BASE_URL not set; skipping public API checks"
fi

if [[ -n "$WEB_BASE_URL" ]]; then
  check "Web root" "curl -fsS '$WEB_BASE_URL' >/dev/null"
else
  echo "⚠️  WEB_BASE_URL not set; skipping public web checks"
fi

if [[ -d "api" ]]; then
  check "API tests (no holdout)" "cd api && (pytest -v --ignore=tests/holdout || .venv/bin/pytest -v --ignore=tests/holdout)"
fi

echo

echo "Summary: $pass passed, $fail failed"
if [[ $fail -gt 0 ]]; then
  exit 1
fi
