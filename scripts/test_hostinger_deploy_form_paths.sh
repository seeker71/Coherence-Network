#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT_DIR/.github/workflows/hostinger-auto-deploy.yml"
DEPLOY_SCRIPT="$ROOT_DIR/deploy/hostinger/auto-deploy.sh"
DOCKERFILE="$ROOT_DIR/Dockerfile.api"
KERNEL_ROUTER_DOCKERFILE="$ROOT_DIR/Dockerfile.kernel-router"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

grep -Fq "'form/form-stdlib/**'" "$WORKFLOW" \
  || fail "Hostinger workflow does not trigger for form/form-stdlib changes"

grep -Fq "'deploy/front-door/**'" "$WORKFLOW" \
  || fail "Hostinger workflow does not trigger for BML front-door catalog changes"

grep -Fq "COPY form/form-stdlib/ ./form/form-stdlib/" "$DOCKERFILE" \
  || fail "API image does not carry form/form-stdlib"

grep -Fq "COPY deploy/front-door/api.bml /routes/api.bml" "$KERNEL_ROUTER_DOCKERFILE" \
  || fail "kernel-router image does not carry the BML front-door catalog"

grep -Fq 'Path(`/api/runtime/events`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the runtime-events BML route"

grep -Fq 'PathRegexp(`^/api/views/stats/[^/]+$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the views-stats BML template route"

grep -Fq 'PathRegexp(`^/api/reactions/concept/[^/]+/summary$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the reaction summary BML template route"

grep -Fq 'PathRegexp(`^/api/reactions/concept/[^/]+/threads$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the reaction threads BML template route"

grep -Fq 'PathRegexp(`^/api/concepts/[^/]+/voices$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the concept voices BML template route"

grep -Fq "BML front-door promoted read routes" "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the promoted BML read routes"

grep -Fq "form/form-stdlib/*)" "$DEPLOY_SCRIPT" \
  || fail "deploy service routing does not send form/form-stdlib changes to api"

grep -Fq "sync_form_stdlib()" "$DEPLOY_SCRIPT" \
  || fail "deploy script does not sync form stdlib into the api container"

if awk '/^is_static_only_change\(\)/,/^}/ { print }' "$DEPLOY_SCRIPT" | grep -Fq "form/*) ;;"; then
  fail "form/* is still treated as static-only"
fi

echo "hostinger form deploy path: PASS"
