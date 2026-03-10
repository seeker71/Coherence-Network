#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
GHX_CMD=("${SCRIPT_DIR}/ghx.sh")

if [[ "${GHX_SKIP_AUTH_CHECK:-0}" == "1" ]]; then
  echo "ghx-auth-check: skipped via GHX_SKIP_AUTH_CHECK=1."
  exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ghx-auth-check: gh CLI not found on PATH."
  exit 1
fi

if [[ ! -x "${GHX_CMD[0]}" ]]; then
  echo "ghx-auth-check: missing executable scripts/ghx.sh"
  exit 1
fi

extract_owner() {
  local remote_url="$1"
  if [[ "$remote_url" =~ ^https?://github\.com/([^/]+)/[^/]+(\.git)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  if [[ "$remote_url" =~ ^git@github\.com:([^/]+)/[^/]+(\.git)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  if [[ "$remote_url" =~ ^ssh://git@github\.com/([^/]+)/[^/]+(\.git)?$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

cd "$REPO_ROOT"

expected_owner=""
for remote_name in origin upstream fork; do
  remote_url="$(git remote get-url "$remote_name" 2>/dev/null || true)"
  if [[ -z "$remote_url" ]]; then
    continue
  fi
  owner="$(extract_owner "$remote_url" || true)"
  if [[ -n "$owner" ]]; then
    expected_owner="$owner"
    break
  fi
done

status_output="$("${GHX_CMD[@]}" auth status -h github.com 2>&1)" || {
  echo "ghx-auth-check: ghx auth status failed."
  echo "$status_output"
  exit 1
}

account_line="$(printf '%s\n' "$status_output" | rg -m1 "Logged in to github.com account" || true)"
if [[ -z "$account_line" ]]; then
  echo "ghx-auth-check: unable to parse account from ghx auth status output."
  echo "$status_output"
  exit 1
fi

active_account="$(printf '%s\n' "$account_line" | sed -E 's/.*account ([^ ]+).*/\1/')"
if [[ -z "$active_account" ]]; then
  echo "ghx-auth-check: parsed empty account from ghx auth status output."
  echo "$status_output"
  exit 1
fi

if [[ -n "$expected_owner" && "$active_account" != "$expected_owner" ]]; then
  echo "ghx-auth-check: active account mismatch."
  echo "  expected_owner=${expected_owner}"
  echo "  active_account=${active_account}"
  echo "Fix profile mapping before continuing."
  exit 1
fi

echo "ghx-auth-check: ok (account=${active_account}${expected_owner:+, expected_owner=${expected_owner}})."
