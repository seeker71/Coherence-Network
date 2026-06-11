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

grep -Fq 'coherence-api-kernel-native-first.rule: "Host(`api.coherencycoin.com`)"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not make the API host native-first"

grep -Fq 'coherence-api-kernel-native-first.service: "coherence-api-kernel-canary"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router native-first ingress does not target the production manifest service"

grep -Fq 'PathRegexp(`^/api/views/stats/[^/]+$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the views-stats BML template route"

grep -Fq 'PathRegexp(`^/api/reactions/concept/[^/]+/summary$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the reaction summary BML template route"

grep -Fq 'PathRegexp(`^/api/reactions/concept/[^/]+/threads$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the reaction threads BML template route"

grep -Fq 'PathRegexp(`^/api/concepts/[^/]+/voices$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the concept voices BML template route"

grep -Fq 'PathRegexp(`^/api/concepts/[^/]+/carried-by$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the concept carried-by BML template route"

grep -Fq 'PathRegexp(`^/api/presences/[^/]+/resonances$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the presence resonances BML template route"

grep -Fq 'Path(`/api/spec-registry`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the spec registry BML list route"

grep -Fq 'PathRegexp(`^/api/spec-registry/[^/]+$`) && !Path(`/api/spec-registry/cards`) && !Path(`/api/spec-registry/source-list`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the spec registry BML detail route with reserved siblings excluded"

grep -Fq 'PathRegexp(`^/api/ideas/[^/]+/specs$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the idea specs BML route"

grep -Fq 'Path(`/api/sensings`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the sensings BML route"

grep -Fq 'Path(`/api/lenses`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the lenses BML route"

grep -Fq 'PathRegexp(`^/api/sensings/[^/]+$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the sensing detail BML template route"

grep -Fq 'PathRegexp(`^/api/translations/[^/]+/[^/]+$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the translations entity BML template route"

grep -Fq "BML front-door promoted read routes" "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the promoted BML read routes"

grep -Fq 'X-Form-Handler: \${handler}' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not require promoted BML handler proof"

grep -Fq 'X-Form-Python-Authority: false' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not require promoted BML authority proof"

grep -Fq 'api_sensings' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the sensings BML handler"

grep -Fq 'api_lenses' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the lenses BML handler"

grep -Fq 'api_concept_carried_by' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the concept carried-by BML handler"

grep -Fq 'api_presence_resonances' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the presence resonances BML handler"

grep -Fq 'api_spec_registry' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the spec registry BML handler"

grep -Fq 'api_spec_registry_detail' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the spec registry detail BML handler"

grep -Fq 'api_idea_specs' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the idea specs BML handler"

grep -Fq 'api_translations_entity' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the translations entity BML handler"

grep -Fq 'api-native-ok-json("api_runtime_events"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "runtime events handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_views_stats"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "views stats handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_reaction_concept_summary"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "reaction summary handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_reaction_concept_threads"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "reaction threads handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_concept_voices"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "concept voices handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_concept_carried_by"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "concept carried-by handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_presence_resonances"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "presence resonances handler does not emit native proof headers"

grep -Fq 'api-spec-list-response("api_spec_registry"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "spec registry handler does not emit native proof headers with x-total-count"

grep -Fq 'api-native-ok-json("api_spec_registry_detail"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "spec registry detail handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_idea_specs"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "idea specs handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_sensings"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "sensings handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_lenses"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "lenses handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_sensing_detail"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "sensing detail handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_translations_entity"' "$ROOT_DIR/deploy/front-door/api.bml" \
  || fail "translations entity handler does not emit native proof headers"

grep -Fq "form/form-stdlib/*)" "$DEPLOY_SCRIPT" \
  || fail "deploy service routing does not send form/form-stdlib changes to api"

grep -Fq "sync_form_stdlib()" "$DEPLOY_SCRIPT" \
  || fail "deploy script does not sync form stdlib into the api container"

if awk '/^is_static_only_change\(\)/,/^}/ { print }' "$DEPLOY_SCRIPT" | grep -Fq "form/*) ;;"; then
  fail "form/* is still treated as static-only"
fi

echo "hostinger form deploy path: PASS"
