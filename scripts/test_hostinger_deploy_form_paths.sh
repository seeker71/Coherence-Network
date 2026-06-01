#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT_DIR/.github/workflows/hostinger-auto-deploy.yml"
DEPLOY_SCRIPT="$ROOT_DIR/deploy/hostinger/auto-deploy.sh"
DOCKERFILE="$ROOT_DIR/Dockerfile.api"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

grep -Fq "'form/form-stdlib/**'" "$WORKFLOW" \
  || fail "Hostinger workflow does not trigger for form/form-stdlib changes"

grep -Fq "COPY form/form-stdlib/ ./form/form-stdlib/" "$DOCKERFILE" \
  || fail "API image does not carry form/form-stdlib"

grep -Fq "form/form-stdlib/*)" "$DEPLOY_SCRIPT" \
  || fail "deploy service routing does not send form/form-stdlib changes to api"

grep -Fq "sync_form_stdlib()" "$DEPLOY_SCRIPT" \
  || fail "deploy script does not sync form stdlib into the api container"

if awk '/^is_static_only_change\(\)/,/^}/ { print }' "$DEPLOY_SCRIPT" | grep -Fq "form/*) ;;"; then
  fail "form/* is still treated as static-only"
fi

echo "hostinger form deploy path: PASS"
