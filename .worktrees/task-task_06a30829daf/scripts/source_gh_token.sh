#!/usr/bin/env bash
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh not found on PATH" >&2
  exit 1
fi

token="$(gh auth token 2>/dev/null || true)"
if [ -z "$token" ]; then
  echo "ERROR: gh auth token unavailable. Run: gh auth login -h github.com" >&2
  exit 1
fi

export GH_TOKEN="$token"
echo "OK: exported GH_TOKEN (len=${#GH_TOKEN})"
