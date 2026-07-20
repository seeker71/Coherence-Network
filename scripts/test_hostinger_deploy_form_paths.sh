#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="$ROOT_DIR/.github/workflows/hostinger-auto-deploy.yml"
DEPLOY_SCRIPT="$ROOT_DIR/deploy/hostinger/auto-deploy.sh"
SUBSTRATE_HOOK="$ROOT_DIR/scripts/substrate_post_merge_hook.sh"
DOCKERFILE="$ROOT_DIR/Dockerfile.api"
KERNEL_ROUTER_DOCKERFILE="$ROOT_DIR/Dockerfile.kernel-router"
WORKER_START="$ROOT_DIR/deploy/worker/start-worker.vbs"
WORKTREE_QUICKSTART="$ROOT_DIR/docs/WORKTREE-QUICKSTART.md"
PROMPT_GATE="$ROOT_DIR/scripts/prompt_entry_gate.sh"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

extract_shell_function() {
  local name="$1" source_file="$2"
  awk -v signature="${name}() {" '
    $0 == signature { capture = 1 }
    capture { print }
    capture && $0 == "}" { exit }
  ' "$source_file"
}

python3 - "$DEPLOY_SCRIPT" <<'PY' || fail "host deploy does not initialize recursive submodules after target selection"
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
reset = next(i for i, line in enumerate(lines) if 'git reset --hard "$TARGET_SHA"' in line)
branch_end = next(i for i in range(reset + 1, len(lines)) if lines[i].strip() == "fi")
sync = next(i for i, line in enumerate(lines) if line.strip() == 'git submodule sync --recursive')
update = next(i for i, line in enumerate(lines) if line.strip() == 'git submodule update --force --init --recursive')
prepare = next(i for i, line in enumerate(lines) if line.strip() == 'python3 scripts/prepare_form_submodule.py --repo-root .')
verify = next(i for i, line in enumerate(lines) if line.strip() == 'python3 scripts/prepare_form_submodule.py --repo-root . --verify-clean')
if not prepare < sync < update < verify:
    raise SystemExit("legacy preservation, sync, update, and pin verification are out of order")
calls = [i for i, line in enumerate(lines) if line.strip() == "sync_pinned_submodules"]
aligned_exit = next(i for i, line in enumerate(lines) if line.strip() == "exit 0" and i > reset - 40)
if not any(i < aligned_exit for i in calls):
    raise SystemExit("already-aligned deploy path exits before initializing submodules")
if not any(i > branch_end for i in calls):
    raise SystemExit("rebuild path does not initialize submodules after target selection")
PY

grep -Fq 'git pull origin main && python scripts\prepare_form_submodule.py --repo-root . && git submodule sync --recursive && git submodule update --force --init --recursive && python scripts\prepare_form_submodule.py --repo-root . --verify-clean && set PYTHONUTF8=1&& python' "$WORKER_START" \
  || fail "Windows worker does not initialize recursive submodules after pull and before Python"

if [[ "$(grep -Fc 'git submodule update --init --recursive' "$WORKTREE_QUICKSTART")" -ne 2 ]]; then
  fail "worktree quickstart does not initialize recursive submodules in both startup flows"
fi

grep -Fq 'prompt-entry-guide: form submodule is not initialized.' "$PROMPT_GATE" \
  || fail "prompt gate does not diagnose an uninitialized form gitlink"

grep -Fq 'git submodule sync --recursive' "$PROMPT_GATE" \
  || fail "prompt gate does not provide the submodule sync remediation"

grep -Fq 'git submodule update --init --recursive' "$PROMPT_GATE" \
  || fail "prompt gate does not provide the submodule update remediation"

PROMPT_GATE_FIXTURE="$(mktemp -d)"
cleanup_prompt_gate_fixture() {
  rm -rf "$PROMPT_GATE_FIXTURE"
}
trap cleanup_prompt_gate_fixture EXIT
mkdir -p "$PROMPT_GATE_FIXTURE/kernel" "$PROMPT_GATE_FIXTURE/repo/scripts"
git -C "$PROMPT_GATE_FIXTURE/kernel" init -q
printf '%s\n' 'reviewed kernel source' >"$PROMPT_GATE_FIXTURE/kernel/core.fk"
git -C "$PROMPT_GATE_FIXTURE/kernel" add core.fk
git -C "$PROMPT_GATE_FIXTURE/kernel" \
  -c user.name='Coherence Test' -c user.email='test@coherencycoin.com' \
  commit -qm seed
git -C "$PROMPT_GATE_FIXTURE/repo" init -q
git -C "$PROMPT_GATE_FIXTURE/repo" -c protocol.file.allow=always \
  submodule add -q "$PROMPT_GATE_FIXTURE/kernel" form
cp "$PROMPT_GATE" "$PROMPT_GATE_FIXTURE/repo/scripts/prompt_entry_gate.sh"
rm -rf "$PROMPT_GATE_FIXTURE/repo/form"
if prompt_gate_output="$(cd "$PROMPT_GATE_FIXTURE/repo" && bash scripts/prompt_entry_gate.sh 2>&1)"; then
  fail "prompt gate accepts an uninitialized form gitlink"
fi
grep -Fq 'prompt-entry-guide: form submodule is not initialized.' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not report the uninitialized form gitlink"
grep -Fq 'git submodule update --init --recursive' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not return the exact update remediation"

git -C "$PROMPT_GATE_FIXTURE/repo" -c protocol.file.allow=always \
  submodule update --init --recursive -q
git -C "$PROMPT_GATE_FIXTURE/kernel" \
  -c user.name='Coherence Test' -c user.email='test@coherencycoin.com' \
  commit --allow-empty -qm newer-kernel
newer_kernel_sha="$(git -C "$PROMPT_GATE_FIXTURE/kernel" rev-parse HEAD)"
git -C "$PROMPT_GATE_FIXTURE/repo/form" fetch -q origin
git -C "$PROMPT_GATE_FIXTURE/repo/form" checkout -q "$newer_kernel_sha"
if prompt_gate_output="$(cd "$PROMPT_GATE_FIXTURE/repo" && bash scripts/prompt_entry_gate.sh 2>&1)"; then
  fail "prompt gate accepts a form checkout that differs from the pinned gitlink"
fi
grep -Fq 'prompt-entry-guide: form submodule is not at the pinned gitlink.' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not report the mismatched form gitlink"
grep -Fq 'git submodule update --force --init --recursive form' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not return the exact pin-restoration command"
git -C "$PROMPT_GATE_FIXTURE/repo" -c protocol.file.allow=always \
  submodule update --force --init --recursive -q
printf '%s\n' 'tracked local change' >>"$PROMPT_GATE_FIXTURE/repo/form/core.fk"
if prompt_gate_output="$(cd "$PROMPT_GATE_FIXTURE/repo" && bash scripts/prompt_entry_gate.sh 2>&1)"; then
  fail "prompt gate accepts tracked changes inside the pinned form checkout"
fi
grep -Fq 'prompt-entry-guide: form submodule has material changes outside the reviewed pin.' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not report tracked form changes"
grep -Fq 'git submodule update --force --init --recursive form' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not return the tracked-dirt restoration command"
git -C "$PROMPT_GATE_FIXTURE/repo/form" checkout -q -- core.fk
printf '%s\n' 'new kernel source' >"$PROMPT_GATE_FIXTURE/repo/form/new-band.fk"
if prompt_gate_output="$(cd "$PROMPT_GATE_FIXTURE/repo" && bash scripts/prompt_entry_gate.sh 2>&1)"; then
  fail "prompt gate accepts untracked source inside the pinned form checkout"
fi
grep -Fq 'prompt-entry-guide: form submodule has material changes outside the reviewed pin.' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not report untracked form source"
grep -Fq '?? new-band.fk' <<<"$prompt_gate_output" \
  || fail "prompt gate fixture did not identify the untracked form source"
cleanup_prompt_gate_fixture
trap - EXIT

# Exercise gitlink-aware routing in isolated local repositories. These fixtures
# never invoke Docker, deploy, or the network; Docker/log are shell stubs.
ROUTING_FIXTURE="$(mktemp -d)"
cleanup_routing_fixture() {
  rm -rf "$ROUTING_FIXTURE"
}
trap cleanup_routing_fixture EXIT
KERNEL_REPO="$ROUTING_FIXTURE/kernel"
SUPER_REPO="$ROUTING_FIXTURE/super"
mkdir -p "$KERNEL_REPO/form-stdlib" "$SUPER_REPO"
git -C "$KERNEL_REPO" init -q
git -C "$KERNEL_REPO" config user.name 'Coherence Test'
git -C "$KERNEL_REPO" config user.email 'test@coherencycoin.com'
printf '%s\n' '(= kernel-band-v1 1)' >"$KERNEL_REPO/form-stdlib/kernel-band.fk"
printf '%s\n' '{}' >"$KERNEL_REPO/form-stdlib/form-ontology.json"
git -C "$KERNEL_REPO" add form-stdlib
git -C "$KERNEL_REPO" commit -qm 'kernel v1'
KERNEL_V1="$(git -C "$KERNEL_REPO" rev-parse HEAD)"

git -C "$SUPER_REPO" init -q
git -C "$SUPER_REPO" config user.name 'Coherence Test'
git -C "$SUPER_REPO" config user.email 'test@coherencycoin.com'
git -C "$SUPER_REPO" -c protocol.file.allow=always submodule add -q "$KERNEL_REPO" form
git -C "$SUPER_REPO" commit -qam 'pin kernel v1'
SUPER_V1="$(git -C "$SUPER_REPO" rev-parse HEAD)"

printf '%s\n' '(= kernel-band-v2 2)' >"$KERNEL_REPO/form-stdlib/kernel-band.fk"
printf '%s\n' '{"version": 2}' >"$KERNEL_REPO/form-stdlib/form-ontology.json"
git -C "$KERNEL_REPO" commit -qam 'kernel v2'
KERNEL_V2="$(git -C "$KERNEL_REPO" rev-parse HEAD)"
git -C "$SUPER_REPO/form" fetch -q origin
git -C "$SUPER_REPO/form" checkout -q "$KERNEL_V2"
git -C "$SUPER_REPO" add form
git -C "$SUPER_REPO" commit -qm 'pin kernel v2'
SUPER_V2="$(git -C "$SUPER_REPO" rev-parse HEAD)"

eval "$(extract_shell_function changed_paths_between "$DEPLOY_SCRIPT")"
eval "$(extract_shell_function services_to_rebuild "$DEPLOY_SCRIPT")"
eval "$(extract_shell_function sync_form_stdlib "$DEPLOY_SCRIPT")"
REPO_DIR="$SUPER_REPO"
expanded_paths="$(changed_paths_between "$SUPER_V1" "$SUPER_V2")"
grep -Fxq 'form' <<<"$expanded_paths" \
  || fail "gitlink path expansion drops the superproject form path"
grep -Fxq 'form/form-stdlib/kernel-band.fk' <<<"$expanded_paths" \
  || fail "gitlink path expansion does not expose changed stdlib recipes"
grep -Fxq 'form/form-stdlib/form-ontology.json' <<<"$expanded_paths" \
  || fail "gitlink path expansion does not expose changed Blueprint tissue"
[[ "$(services_to_rebuild "$SUPER_V1" "$SUPER_V2")" == "api" ]] \
  || fail "an exact form gitlink bump does not route to an API rebuild"

DOCKER_CALLS="$ROUTING_FIXTURE/docker.calls"
LOG_FILE="$ROUTING_FIXTURE/deploy.log"
DIFF_BASE="$SUPER_V1"
TARGET_SHA="$SUPER_V2"
docker() {
  printf '%s\n' "$*" >>"$DOCKER_CALLS"
}
log() {
  printf '%s\n' "$*" >>"$LOG_FILE"
}
sync_form_stdlib
grep -Fq "compose cp $SUPER_REPO/form/form-stdlib api:/app/form/form-stdlib" "$DOCKER_CALLS" \
  || fail "stdlib sync does not run for an exact form gitlink bump"

unset -f changed_paths_between
eval "$(extract_shell_function sync_pinned_submodules "$SUBSTRATE_HOOK")"
eval "$(extract_shell_function changed_paths_between "$SUBSTRATE_HOOK")"
eval "$(extract_shell_function changed_path_routes "$SUBSTRATE_HOOK")"

# The first migration can leave ignored build outputs in the formerly tracked
# form/ directory. Preserve those local artifacts, then initialize the gitlink.
TRANSITION_REPO="$ROUTING_FIXTURE/transition-super"
mkdir -p "$TRANSITION_REPO/form" "$TRANSITION_REPO/scripts"
cp "$ROOT_DIR/scripts/prepare_form_submodule.py" "$TRANSITION_REPO/scripts/"
git -C "$TRANSITION_REPO" init -q
git -C "$TRANSITION_REPO" config user.name 'Coherence Test'
git -C "$TRANSITION_REPO" config user.email 'test@coherencycoin.com'
printf '%s\n' 'form/generated.cache' >"$TRANSITION_REPO/.gitignore"
printf '%s\n' 'old tracked kernel source' >"$TRANSITION_REPO/form/old.fk"
git -C "$TRANSITION_REPO" add .gitignore form/old.fk
git -C "$TRANSITION_REPO" commit -qm 'tracked form tree'
TRANSITION_OLD="$(git -C "$TRANSITION_REPO" rev-parse HEAD)"
git -C "$TRANSITION_REPO" rm -qr form/old.fk
printf '%s\n' \
  '[submodule "form"]' \
  '  path = form' \
  "  url = $KERNEL_REPO" \
  >"$TRANSITION_REPO/.gitmodules"
git -C "$TRANSITION_REPO" add .gitmodules
git -C "$TRANSITION_REPO" update-index --add --cacheinfo 160000 "$KERNEL_V2" form
git -C "$TRANSITION_REPO" commit -qm 'replace tracked tree with gitlink'
TRANSITION_NEW="$(git -C "$TRANSITION_REPO" rev-parse HEAD)"
git -C "$TRANSITION_REPO" checkout -q "$TRANSITION_OLD"
printf '%s\n' 'valuable local build output' >"$TRANSITION_REPO/form/generated.cache"
git -C "$TRANSITION_REPO" checkout -q "$TRANSITION_NEW" 2>/dev/null
[[ ! -e "$TRANSITION_REPO/form/.git" ]] \
  || fail "transition fixture unexpectedly initialized the submodule"
(cd "$TRANSITION_REPO" && GIT_ALLOW_PROTOCOL=file sync_pinned_submodules)
[[ "$(git -C "$TRANSITION_REPO/form" rev-parse HEAD)" == "$KERNEL_V2" ]] \
  || fail "tracked-tree transition did not initialize the pinned kernel"
preserved_cache="$(find "$TRANSITION_REPO/.cache" -path '*/form-pre-submodule-*/generated.cache' -print -quit)"
[[ -n "$preserved_cache" && -f "$preserved_cache" ]] \
  || fail "tracked-tree transition did not preserve ignored form artifacts"

# A post-merge hook sees the new superproject pin while the submodule checkout
# still points at the old commit. The hook itself must close that gap before it
# reads or ingests Form tissue.
git -C "$SUPER_REPO/form" checkout -q "$KERNEL_V1"
mkdir -p "$SUPER_REPO/scripts"
cp "$ROOT_DIR/scripts/prepare_form_submodule.py" "$SUPER_REPO/scripts/"
[[ "$(git -C "$SUPER_REPO/form" rev-parse HEAD)" == "$KERNEL_V1" ]] \
  || fail "stale post-merge fixture did not start at the old kernel pin"
(cd "$SUPER_REPO" && GIT_ALLOW_PROTOCOL=file sync_pinned_submodules)
[[ "$(git -C "$SUPER_REPO/form" rev-parse HEAD)" == "$KERNEL_V2" ]] \
  || fail "post-merge hook did not hydrate the new pinned kernel before ingest"
printf '%s\n' 'tracked dirt' >>"$SUPER_REPO/form/form-stdlib/kernel-band.fk"
if (cd "$SUPER_REPO" && GIT_ALLOW_PROTOCOL=file sync_pinned_submodules); then
  fail "post-merge hook accepts tracked changes inside the form checkout"
fi
git -C "$SUPER_REPO/form" restore form-stdlib/kernel-band.fk
printf '%s\n' 'new unreviewed kernel source' >"$SUPER_REPO/form/form-stdlib/unreviewed-band.fk"
if (cd "$SUPER_REPO" && GIT_ALLOW_PROTOCOL=file sync_pinned_submodules); then
  fail "post-merge hook accepts untracked source inside the form checkout"
fi
rm "$SUPER_REPO/form/form-stdlib/unreviewed-band.fk"
mkdir -p "$SUPER_REPO/form/.cache"
printf '%s\n' 'disposable crash report' >"$SUPER_REPO/form/.cache/crash.json"
(cd "$SUPER_REPO" && GIT_ALLOW_PROTOCOL=file sync_pinned_submodules) \
  || fail "post-merge hook rejects allowlisted form cache output"
hook_paths="$(cd "$SUPER_REPO" && changed_paths_between "$SUPER_V1" "$SUPER_V2")"
hook_routes="$(changed_path_routes "$hook_paths")"
grep -Fxq blueprint <<<"$hook_routes" \
  || fail "Blueprint projection does not recognize an internal registry change"
if grep -Fxq training <<<"$hook_routes"; then
  fail "consumer hook tries to capture coherence-kernel commits from a superproject range"
fi
grep -Fxq rag <<<"$hook_routes" \
  || fail "RAG healing does not recognize an internal Form recipe change"

# Simulate a shallow submodule that has the new pin but not the old one. The
# helper must conservatively enumerate the full new snapshot, not lose routing.
rm -rf "$SUPER_REPO/form" "$SUPER_REPO/.git/modules/form"
git clone -q --depth 1 "file://$KERNEL_REPO" "$SUPER_REPO/form"
if git -C "$SUPER_REPO/form" cat-file -e "${KERNEL_V1}^{commit}" 2>/dev/null; then
  fail "shallow fixture unexpectedly retained the old kernel commit"
fi
fallback_paths="$(cd "$SUPER_REPO" && changed_paths_between "$SUPER_V1" "$SUPER_V2")"
grep -Fxq 'form/form-stdlib/kernel-band.fk' <<<"$fallback_paths" \
  || fail "missing old gitlink commit does not fall back to the full new snapshot"
fallback_routes="$(changed_path_routes "$fallback_paths")"
grep -Fxq blueprint <<<"$fallback_routes" \
  || fail "full-snapshot fallback does not preserve Blueprint routing"
if grep -Fxq training <<<"$fallback_routes"; then
  fail "full-snapshot fallback routes coherence-kernel sources through superproject training"
fi
grep -Fxq rag <<<"$fallback_routes" \
  || fail "full-snapshot fallback does not preserve RAG routing"

cleanup_routing_fixture
trap - EXIT

grep -Fq "'form/form-stdlib/**'" "$WORKFLOW" \
  || fail "Hostinger workflow does not trigger for form/form-stdlib changes"

grep -Fq "'deploy/front-door/**'" "$WORKFLOW" \
  || fail "Hostinger workflow does not trigger for BML front-door catalog changes"

grep -Fq "COPY form/form-stdlib/ ./form/form-stdlib/" "$DOCKERFILE" \
  || fail "API image does not carry form/form-stdlib"

grep -Fq "COPY form/apps/coherence-network/api.bml /routes/api.bml" "$KERNEL_ROUTER_DOCKERFILE" \
  || fail "kernel-router image does not carry the BML front-door catalog"

grep -Fq 'Path(`/api/runtime/events`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the runtime-events BML route"

grep -Fq 'coherence-api-kernel-native-first.rule: "Host(`api.coherencycoin.com`) && !PathPrefix(`/api/deployment-observer/`) && !QueryRegexp(`observation_nonce`,`^[A-Za-z0-9_-]{43}$`)"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not make the API host native-first"
grep -Fq '!PathPrefix(`/api/deployment-observer/`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not reserve the authenticated observer control plane for the API"
grep -Fq '!QueryRegexp(`observation_nonce`,`^[A-Za-z0-9_-]{43}$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not reserve nonce-bound public health observation for the API"

grep -Fq 'coherence-api-kernel-native-first.service: "coherence-api-kernel-canary"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router native-first ingress does not target the production manifest service"

grep -Fq 'coherence-api-kernel-native-first.priority: "1160"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router native-first ingress no longer sits above the base API router and below BML-specific routes"

grep -Fq 'coherence-api-kernel-runtime-attention.rule: "Host(`api.coherencycoin.com`) && Method(`GET`) && Path(`/api/attention/kernel-runtime`)"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the production-manifest attention probe"

grep -Fq 'coherence-api-kernel-runtime-attention.service: "coherence-api-kernel-canary"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router attention probe ingress does not target the production manifest service"

grep -Fq 'coherence-api-bml-runtime-attention.service: "coherence-api-kernel-bml-front-door"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router BML attention ingress does not target the stable BML front door"

grep -Fq 'coherence-api-bml-runtime-attention.priority: "1186"' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router BML attention ingress does not sit above the production-manifest attention route"

grep -Fq 'observed_fanout_path_count' "$ROOT_DIR/deploy/kernel-router/production-routes.fk" \
  || fail "kernel-runtime attention route no longer reports the bounded fanout path count"

grep -Fq 'fanout_path_counts\":[]' "$ROOT_DIR/deploy/kernel-router/production-routes.fk" \
  || fail "kernel-runtime attention route no longer bounds fanout_path_counts"

if grep -Fq 'choice_successes choice_failures fanout_path_counts)' "$ROOT_DIR/deploy/kernel-router/production-routes.fk"; then
  fail "kernel-runtime attention measurements reintroduced unbounded fanout_path_counts expansion"
fi

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

grep -Fq 'PathRegexp(`^/api/presences/[^/]+/places$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the presence places BML template route"

grep -Fq '(PathRegexp(`^/api/graph/nodes/[^/]+$`) && !Path(`/api/graph/nodes/count`))' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the graph node detail BML template route without swallowing count"

grep -Fq '(PathRegexp(`^/api/ideas/[^/]+$`) && !Path(`/api/ideas/storage`) && !Path(`/api/ideas/tags`) && !Path(`/api/ideas/cards`) && !Path(`/api/ideas/health`) && !Path(`/api/ideas/right-sizing`) && !Path(`/api/ideas/showcase`) && !Path(`/api/ideas/resonance`) && !Path(`/api/ideas/count`) && !Path(`/api/ideas/progress`) && !Path(`/api/ideas/portfolio-summary`) && !Path(`/api/ideas/breath-overview`))' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the idea detail BML template route without swallowing static idea routes"

grep -Fq 'PathRegexp(`^/api/graph/nodes/[^/]+/edges$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the graph node edges BML template route"

grep -Fq 'Path(`/api/spec-registry`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the spec registry BML list route"

grep -Fq 'PathRegexp(`^/api/spec-registry/[^/]+$`) && !Path(`/api/spec-registry/cards`) && !Path(`/api/spec-registry/source-list`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the spec registry BML detail route with reserved siblings excluded"

grep -Fq 'PathRegexp(`^/api/ideas/[^/]+/specs$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the idea specs BML route"

grep -Fq 'Method(`PATCH`) && PathRegexp(`^/api/ideas/[^/]+$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the idea update BML route"

grep -Fq 'PathRegexp(`^/api/ideas/[^/]+/questions$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the idea question create BML route"

grep -Fq 'PathRegexp(`^/api/ideas/[^/]+/questions/answer$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the idea question answer BML route"

grep -Fq 'Path(`/api/sensings`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the sensings BML route"

grep -Fq 'Path(`/api/lenses`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the lenses BML route"

grep -Fq 'PathRegexp(`^/api/sensings/[^/]+$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the sensing detail BML template route"

grep -Fq 'PathRegexp(`^/api/translations/[^/]+/[^/]+$`)' "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" \
  || fail "kernel-router ingress does not expose the translations entity BML template route"

if ! python3 - "$ROOT_DIR/form/apps/coherence-network/api.bml" "$ROOT_DIR/deploy/kernel-router/docker-compose.kernel-router.yml" <<'PY'
import re
import sys
from pathlib import Path

catalog = Path(sys.argv[1]).read_text(encoding="utf-8")
compose = Path(sys.argv[2]).read_text(encoding="utf-8")

routes = []
for match in re.finditer(
    r'route\("([^"]+)",\s*"([A-Z]+)",\s*"([^"]+)",\s*\d+,\s*"([^"]+)",\s*"([^"]*)"',
    catalog,
):
    name, method, path, handler, header = match.groups()
    if method == "GET":
        routes.append((name, path, header))

if len(routes) < 50:
    raise SystemExit(f"BML GET/read route batch too small: {len(routes)}")

def expected_token(path: str) -> str:
    if path == "/api/spec-registry/{spec_id}":
        return "PathRegexp(`^/api/spec-registry/[^/]+$`) && !Path(`/api/spec-registry/cards`) && !Path(`/api/spec-registry/source-list`)"
    if path == "/api/graph/nodes/{node_id}":
        return "(PathRegexp(`^/api/graph/nodes/[^/]+$`) && !Path(`/api/graph/nodes/count`))"
    if path == "/api/ideas/{idea_id}":
        return "(PathRegexp(`^/api/ideas/[^/]+$`) && !Path(`/api/ideas/storage`) && !Path(`/api/ideas/tags`) && !Path(`/api/ideas/cards`) && !Path(`/api/ideas/health`) && !Path(`/api/ideas/right-sizing`) && !Path(`/api/ideas/showcase`) && !Path(`/api/ideas/resonance`) && !Path(`/api/ideas/count`) && !Path(`/api/ideas/progress`) && !Path(`/api/ideas/portfolio-summary`) && !Path(`/api/ideas/breath-overview`))"
    if path == "/api/agent/tasks/{task_id}":
        return "(PathRegexp(`^/api/agent/tasks/[^/]+$`) && !Path(`/api/agent/tasks/active`) && !Path(`/api/agent/tasks/activity`) && !Path(`/api/agent/tasks/attention`) && !Path(`/api/agent/tasks/count`))"
    if path == "/api/concepts/lc-*":
        return "PathRegexp(`^/api/concepts/lc-[^/]+$`)"
    if path == "/api/presence/*":
        return "PathRegexp(`^/api/presence/[^/]+$`)"
    if path == "/api/field-stories/*":
        return "PathRegexp(`^/api/field-stories/.+$`)"
    if "{" in path:
        pattern = re.sub(r"\{[^/{}]+\}", "[^/]+", path)
        return f"PathRegexp(`^{pattern}$`)"
    return f"Path(`{path}`)"

missing = [(name, path, expected_token(path)) for name, path, _header in routes if expected_token(path) not in compose]
if missing:
    for name, path, token in missing:
        print(f"missing {name}: {path} expected {token}", file=sys.stderr)
    raise SystemExit(1)

required_batches = [
    "coherence-api-bml-read-core-batch",
    "coherence-api-bml-read-ideas-agent-batch",
    "coherence-api-bml-read-relation-batch",
    "coherence-api-bml-read-sensing-batch",
    "coherence-api-bml-read-operations-batch",
    "coherence-api-bml-read-observe-batch",
]
missing_batches = [name for name in required_batches if name not in compose]
if missing_batches:
    raise SystemExit(f"missing BML read batch routers: {missing_batches}")

print(f"BML GET/read ingress coverage: {len(routes)} routes")
PY
then
  fail "kernel-router ingress does not cover every BML GET/read route"
fi

grep -Fq "BML front-door promoted read routes" "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the promoted BML read routes"

grep -Fq 'printf '\''%s'\'' '\''$kernel_image_payload'\'' >/tmp/kernel-image.request.json' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not write the kernel image proposal payload as a request file"

grep -Fq '&& curl -fsS --max-time 30 -D /tmp/kernel-image.headers' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not allow the cold kernel image proposal route enough time"

grep -Fq -- '--data-binary @/tmp/kernel-image.request.json' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not post the kernel image proposal payload from a request file"

grep -Fq "kernel-image body:" "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not print kernel image proposal diagnostics on failure"

grep -Fq 'X-Form-Handler: \${handler}' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not require promoted BML handler proof"

grep -Fq 'X-Form-Python-Authority: false' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not require promoted BML authority proof"

grep -Fq 'curl -fsS --max-time 10 -D /tmp/promoted-' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not bound promoted BML read route curl probes"

grep -Fq 'api_sensings' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the sensings BML handler"

grep -Fq 'api_lenses' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the lenses BML handler"

grep -Fq 'api_concept_carried_by' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the concept carried-by BML handler"

grep -Fq 'api_presence_resonances' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the presence resonances BML handler"

grep -Fq 'api_presence_places' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the presence places BML handler"

grep -Fq 'api_graph_node_detail' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the graph node detail BML handler"

grep -Fq 'api_idea_detail' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the idea detail BML handler"

grep -Fq 'api_graph_node_edges' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the graph node edges BML handler"

grep -Fq 'api_spec_registry' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the spec registry BML handler"

grep -Fq 'api_spec_registry_detail' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the spec registry detail BML handler"

grep -Fq 'api_idea_specs' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the idea specs BML handler"

grep -Fq 'api_attention_kernel_runtime' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the BML runtime attention handler"

grep -Fq 'api_translations_entity' "$DEPLOY_SCRIPT" \
  || fail "deploy canary does not probe the translations entity BML handler"

grep -Fq 'api-native-ok-json("api_runtime_events"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "runtime events handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_views_stats"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "views stats handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_reaction_concept_summary"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "reaction summary handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_reaction_concept_threads"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "reaction threads handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_concept_voices"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "concept voices handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_concept_carried_by"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "concept carried-by handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_presence_resonances"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "presence resonances handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_presence_places"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "presence places handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_graph_node_detail"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "graph node detail handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_idea_detail"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea detail handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_idea_update"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea update handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_idea_question_create"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea question create handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_idea_question_answer"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea question answer handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_graph_node_edges"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "graph node edges handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_agent_task_log"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "agent task log handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_attention_kernel_runtime"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "runtime attention handler does not emit native proof headers"

grep -Fq 'language-route-class-kernel-route(AgentTaskLogRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "agent task log route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(PresencePlacesRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "presence places route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(GraphNodeDetailRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "graph node detail route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(IdeaDetailRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea detail route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(IdeaUpdateRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea update route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(IdeaQuestionCreateRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea question create route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(IdeaQuestionAnswerRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea question answer route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(KernelRuntimeAttentionRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "runtime attention route class is not exported in the BML routes list"

grep -Fq 'language-route-class-kernel-route(GraphNodeEdgesRoute)' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "graph node edges route class is not exported in the BML routes list"

grep -Fq 'api-spec-list-response("api_spec_registry"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "spec registry handler does not emit native proof headers with x-total-count"

grep -Fq 'api-native-ok-json("api_spec_registry_detail"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "spec registry detail handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_idea_specs"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "idea specs handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_sensings"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "sensings handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_lenses"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "lenses handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_sensing_detail"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "sensing detail handler does not emit native proof headers"

grep -Fq 'api-native-ok-json("api_translations_entity"' "$ROOT_DIR/form/apps/coherence-network/api.bml" \
  || fail "translations entity handler does not emit native proof headers"

grep -Fq "form/form-stdlib/*)" "$DEPLOY_SCRIPT" \
  || fail "deploy service routing does not send form/form-stdlib changes to api"

grep -Fq "sync_form_stdlib()" "$DEPLOY_SCRIPT" \
  || fail "deploy script does not sync form stdlib into the api container"

if awk '/^is_static_only_change\(\)/,/^}/ { print }' "$DEPLOY_SCRIPT" | grep -Fq "form/*) ;;"; then
  fail "form/* is still treated as static-only"
fi

grep -Fq '/root/.coherence-network/rag-index' "$ROOT_DIR/Dockerfile.api" \
  || fail "API image does not pre-create the writable RAG index mountpoint"

for state_dir in rag-index rag-requests attestation api-queries; do
  grep -Fq "/root/.coherence-network/$state_dir" "$ROOT_DIR/Dockerfile.api" \
    || fail "API image does not pre-create grounding mountpoint: $state_dir"
done

echo "hostinger form deploy path: PASS"
