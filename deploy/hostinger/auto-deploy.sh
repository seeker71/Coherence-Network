#!/usr/bin/env bash
set -euo pipefail

COMPOSE_ROOT="${COMPOSE_ROOT:-/docker/coherence-network}"
REPO_DIR="${REPO_DIR:-${COMPOSE_ROOT}/repo}"
BRANCH="${BRANCH:-main}"
TARGET_SHA="${1:-}"
LOG_FILE="${LOG_FILE:-${COMPOSE_ROOT}/deploy.log}"
KERNEL_CANARY_COMPOSE_FILE="${KERNEL_CANARY_COMPOSE_FILE:-${REPO_DIR}/deploy/kernel-router/docker-compose.kernel-router.yml}"

timestamp() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

log() {
  printf '%s — %s\n' "$(timestamp)" "$*" | tee -a "$LOG_FILE"
}

# A deploy cancelled mid-recreate (concurrency cancel-in-progress) can leave
# sibling services stopped while the repo and the api container sit aligned
# at the target SHA — web and pulse down, every Traefik route for them dark,
# and the witness unable to report the silence it is part of. That exact
# state shipped on 2026-06-10: the 14:14Z rollout was cancelled by the next
# push, web never came back, and the next run's "Already flowing" exited 0.
# So every path through this script calls this: start whatever is stopped
# (up -d is idempotent for running services), hard-require the public organs
# (api, web), and name the witness loudly when it is down — a dark witness
# verifies blind.
ensure_all_services_up() {
  local running missing svc
  running="$(docker compose -f "$COMPOSE_ROOT/docker-compose.yml" ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk '$2=="running" {print $1}')"
  missing=""
  for svc in api web pulse; do
    if ! printf '%s\n' "$running" | grep -qx "$svc"; then
      missing="${missing} ${svc}"
    fi
  done
  if [[ -z "$missing" ]]; then
    return 0
  fi
  log "services down:${missing} — raising the whole body (docker compose up -d)"
  if ! docker compose -f "$COMPOSE_ROOT/docker-compose.yml" up -d --wait --wait-timeout 180 2>&1 | tee -a "$LOG_FILE"; then
    log "compose up --wait failed or unsupported; falling back to plain up -d"
    docker compose -f "$COMPOSE_ROOT/docker-compose.yml" up -d 2>&1 | tee -a "$LOG_FILE" || true
  fi
  local deadline=$(( $(date +%s) + 180 ))
  for svc in api web; do
    while ! docker compose -f "$COMPOSE_ROOT/docker-compose.yml" ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$svc" '$1==s && $2=="running"' | grep -q .; do
      if (( $(date +%s) >= deadline )); then
        log "FAIL: $svc did not reach running state after raise"
        return 1
      fi
      sleep 3
    done
  done
  if ! docker compose -f "$COMPOSE_ROOT/docker-compose.yml" ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk '$1=="pulse" && $2=="running"' | grep -q .; then
    log "WARN: pulse (the witness) is still not running — the body deploys blind until it breathes"
  fi
  log "all core services running"
}

run_with_timeout() {
  local seconds="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "${seconds}s" "$@"
  else
    "$@"
  fi
}

bootstrap_and_verify_local_grounding() {
  # Deployment owns making the native body operational. Certification belongs
  # to the later GitHub-runner public observation, never to this host-local step.
  if ! docker compose -f "$COMPOSE_ROOT/docker-compose.yml" exec -T api \
      sh -lc '
        set -eu
        cd /app
        for state_dir in rag-index rag-requests attestation api-queries; do
          test -d "/root/.coherence-network/$state_dir"
          probe="/root/.coherence-network/$state_dir/.deploy-write-probe.$$"
          : > "$probe"
          rm -f "$probe"
        done
        python3 scripts/coh_substrate.py bootstrap
        bash scripts/ensure_form_cli_native.sh
        python3 scripts/form_cli_rag.py heal
        out="$(mktemp)"
        err="$(mktemp)"
        trap '\''rm -f "$out" "$err"'\'' EXIT
        bin/form-cli ask "observed auto learning reversible experiment champion challenger" >"$out" 2>"$err"
        grep -Eq "^trust  path:native  grounded:yes .*suffic:yes" "$err"
        grep -Eq "^grounded:@[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+$" "$out"
        cat "$err"
        cat "$out"
      ' 2>&1 | tee -a "$LOG_FILE"; then
    log "FAIL: complete substrate/RAG bootstrap or local native grounded ask failed"
    return 1
  fi
  log "Local grounding: complete corpus indexed and native ask proven ✓"
}

require_file() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    log "FAIL: missing required path $path"
    exit 1
  fi
}

require_file "$REPO_DIR/.git"
require_file "$COMPOSE_ROOT/docker-compose.yml"
require_file "$COMPOSE_ROOT/.env"

HATI_WEB_HOSTS_CHANGED=0

ensure_hati_web_hosts() {
  local result
  result="$(COMPOSE_FILE="$COMPOSE_ROOT/docker-compose.yml" python3 - <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path

compose_path = Path(os.environ["COMPOSE_FILE"])
lines = compose_path.read_text().splitlines()


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def find_service(name: str) -> tuple[int, int, int]:
    services_i = -1
    services_indent = 0
    for i, line in enumerate(lines):
        if line.strip() == "services:":
            services_i = i
            services_indent = indent_of(line)
            break
    if services_i < 0:
        raise RuntimeError("services: block not found")

    service_i = -1
    service_indent = 0
    for i in range(services_i + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped:
            continue
        indent = indent_of(lines[i])
        if indent <= services_indent:
            break
        if indent == services_indent + 2 and stripped == f"{name}:":
            service_i = i
            service_indent = indent
            break
    if service_i < 0:
        raise RuntimeError(f"{name}: service not found")

    service_end = len(lines)
    for i in range(service_i + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if indent_of(lines[i]) <= service_indent:
            service_end = i
            break
    return service_i, service_end, service_indent


labels = {
    "traefik.http.routers.coherence-web-hati.rule": "Host(`hati.earth`) || Host(`www.hati.earth`) || Host(`sense.hati.earth`) || Host(`suci.hati.earth`)",
    "traefik.http.routers.coherence-web-hati.entrypoints": "websecure",
    "traefik.http.routers.coherence-web-hati.tls.certresolver": "letsencrypt",
    "traefik.http.routers.coherence-web-hati.service": "coherence-web-hati",
    "traefik.http.services.coherence-web-hati.loadbalancer.server.port": "3000",
}

try:
    _web_i, web_end, web_indent = find_service("web")
except Exception as exc:
    print(f"error: {exc}", file=sys.stderr)
    sys.exit(1)

labels_i = -1
labels_indent = web_indent + 2
for i in range(_web_i + 1, web_end):
    if lines[i].strip() == "labels:":
        labels_i = i
        labels_indent = indent_of(lines[i])
        break

changed = False
if labels_i < 0:
    insert = [f"{' ' * (web_indent + 2)}labels:"]
    insert.extend(
        f"{' ' * (web_indent + 4)}{key}: \"{value}\""
        for key, value in labels.items()
    )
    lines[web_end:web_end] = insert
    changed = True
else:
    labels_end = web_end
    for i in range(labels_i + 1, web_end):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if indent_of(lines[i]) <= labels_indent:
            labels_end = i
            break

    block = lines[labels_i + 1 : labels_end]
    first_child = next((line.strip() for line in block if line.strip()), "")
    list_style = first_child.startswith("-")
    target_keys = tuple(labels.keys())
    without_hati = [
        line for line in block if not any(key in line for key in target_keys)
    ]
    child_indent = labels_indent + 2
    if list_style:
        target = [
            f"{' ' * child_indent}- \"{key}={value}\""
            for key, value in labels.items()
        ]
    else:
        target = [
            f"{' ' * child_indent}{key}: \"{value}\""
            for key, value in labels.items()
        ]
    new_block = without_hati + target
    if new_block != block:
        lines[labels_i + 1 : labels_end] = new_block
        changed = True

if changed:
    compose_path.write_text("\n".join(lines) + "\n")
    print("changed")
else:
    print("unchanged")
PY
)"
  case "$result" in
    changed)
      HATI_WEB_HOSTS_CHANGED=1
      log "Hati web hosts: added/normalized Traefik router labels for hati.earth and sense/suci subdomains"
      ;;
    unchanged)
      log "Hati web hosts: Traefik router labels already present"
      ;;
    *)
      log "FATAL Hati web hosts: unexpected result '$result'"
      return 1
      ;;
  esac
}

ensure_hati_web_hosts || exit 1

cd "$REPO_DIR"

sync_pinned_submodules() {
  # Preserve any ignored output left by the one-time tracked-tree -> gitlink
  # transition before asking Git to materialize the reviewed kernel snapshot.
  python3 scripts/prepare_form_submodule.py --repo-root .
  git submodule sync --recursive
  git submodule update --force --init --recursive
  python3 scripts/prepare_form_submodule.py --repo-root . --verify-clean
}

# A submodule update is represented in the superproject as the single path
# `form`. Expand that gitlink change through the pinned old/new kernel commits
# so every downstream path router keeps seeing repository-relative paths. When
# the old commit is unavailable (for example, a shallow first deploy), list the
# complete new snapshot; when even the new snapshot cannot be read, return an
# explicit sentinel so callers take their conservative full-refresh path.
changed_paths_between() {
  local from="$1" to="$2"
  local changed nested old_entry new_entry old_mode new_mode old_oid new_oid

  if ! changed="$(cd "$REPO_DIR" && git diff --name-only "$from".."$to" 2>/dev/null)"; then
    return 1
  fi
  printf '%s\n' "$changed" | sed '/^$/d'
  if ! grep -Fxq 'form' <<< "$changed"; then
    return 0
  fi

  old_entry="$(cd "$REPO_DIR" && git ls-tree "$from" -- form 2>/dev/null || true)"
  new_entry="$(cd "$REPO_DIR" && git ls-tree "$to" -- form 2>/dev/null || true)"
  read -r old_mode _ old_oid _ <<< "$old_entry"
  read -r new_mode _ new_oid _ <<< "$new_entry"

  if [[ "$old_mode" == "160000" && "$new_mode" == "160000" ]] \
    && git -C "$REPO_DIR/form" cat-file -e "${old_oid}^{commit}" 2>/dev/null \
    && git -C "$REPO_DIR/form" cat-file -e "${new_oid}^{commit}" 2>/dev/null; then
    if nested="$(git -C "$REPO_DIR/form" diff --name-only "$old_oid".."$new_oid" 2>/dev/null)"; then
      printf '%s\n' "$nested" | sed '/^$/d; s#^#form/#'
      return 0
    fi
  fi

  if [[ "$new_mode" == "160000" ]] \
    && git -C "$REPO_DIR/form" cat-file -e "${new_oid}^{commit}" 2>/dev/null; then
    if nested="$(git -C "$REPO_DIR/form" ls-tree -r --name-only "$new_oid" 2>/dev/null)"; then
      printf '%s\n' "$nested" | sed '/^$/d; s#^#form/#'
      return 0
    fi
  fi

  printf '%s\n' 'form/.gitlink-diff-unavailable'
}

OLD_SHA="$(git rev-parse HEAD)"
log "Deploy begin — old_sha=${OLD_SHA:0:12} target_sha=${TARGET_SHA:-(resolving)} branch=${BRANCH}"
git fetch --prune origin "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" --quiet

if [[ -z "$TARGET_SHA" ]]; then
  TARGET_SHA="$(git rev-parse "origin/${BRANCH}")"
fi

if ! git cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null; then
  log "Target ${TARGET_SHA:0:12} missing after branch fetch; fetching explicit target"
  if ! git fetch origin "$TARGET_SHA" --quiet; then
    if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
      log "Explicit target fetch failed; unshallowing ${BRANCH}"
      git fetch origin "$BRANCH" --unshallow --quiet || true
    fi
  fi
fi
git cat-file -e "${TARGET_SHA}^{commit}"

# Sense whether the RUNNING API is already at the target SHA. The previous
# guard only compared the repo's git HEAD to the target and skipped deploy
# when they matched — but that answered the wrong question. What the field
# needs to know is whether the CONTAINERS are serving the target code, not
# whether the filesystem mirrors it. When a manual `git pull` on the VPS
# advances the repo without rebuilding, subsequent deploys saw "no changes"
# and never rebuilt, so the running API stayed on the old SHA while the
# verification step kept failing. This query asks the living container.
RUNNING_SHA=""
HEALTH_JSON="$(docker compose -f "$COMPOSE_ROOT/docker-compose.yml" exec -T api \
    sh -lc 'curl -fsS --max-time 5 http://127.0.0.1:8000/api/health 2>/dev/null' \
    2>/dev/null || true)"
if [[ -n "$HEALTH_JSON" ]]; then
  RUNNING_SHA="$(printf '%s' "$HEALTH_JSON" \
    | python3 -c 'import sys, json
try:
    print((json.loads(sys.stdin.read()).get("deployed_sha") or "").strip())
except Exception:
    pass' 2>/dev/null || true)"
fi
RUNNING_SHORT="${RUNNING_SHA:0:12}"
[[ -z "$RUNNING_SHORT" ]] && RUNNING_SHORT="unknown"

if [[ "$OLD_SHA" == "$TARGET_SHA" && "$RUNNING_SHA" == "$TARGET_SHA" ]]; then
  sync_pinned_submodules
  log "Already flowing at ${TARGET_SHA:0:12} (repo and running API aligned)"
  # `ensure_hati_web_hosts` may find the labels already present because a
  # previous deploy wrote them into docker-compose.yml but did not include
  # the web service in `compose up`. A plain `up -d web` is idempotent when
  # the live container is already aligned, and it is the missing step that
  # lets Traefik ingest label-only host changes.
  log "Hati web hosts: reconciling web service labels"
  docker compose -f "$COMPOSE_ROOT/docker-compose.yml" up -d web 2>&1 | tee -a "$LOG_FILE"
  # Aligned repo + api is necessary, not sufficient — raise any stopped
  # siblings (web, pulse) before resting, or this exit masks their silence.
  ensure_all_services_up || exit 1
  # A rerun after a witness/index failure must heal and prove the already-live
  # release; SHA alignment alone is not completion.
  bootstrap_and_verify_local_grounding || exit 1
  exit 0
fi

if [[ "$OLD_SHA" == "$TARGET_SHA" ]]; then
  log "Repo aligned at ${TARGET_SHA:0:12} but running API is at ${RUNNING_SHORT} — rebuilding containers"
else
  log "Deploying ${OLD_SHA:0:12} -> ${TARGET_SHA:0:12} (running API at ${RUNNING_SHORT})"
  git reset --hard "$TARGET_SHA" >/dev/null
  git clean -fd >/dev/null
fi

sync_pinned_submodules

FORM_SOURCE_SHA="$(git -C "$REPO_DIR" rev-parse "${TARGET_SHA}:form")"
if [[ ! "$FORM_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  log "FATAL: target form gitlink is not a full commit SHA"
  exit 1
fi

python3 - <<PY
from pathlib import Path

sha = "${TARGET_SHA}"
env_path = Path("${COMPOSE_ROOT}/.env")
lines = env_path.read_text().splitlines()
keys = {
    "GIT_COMMIT_SHA": sha,
    "DEPLOYED_SHA": sha,
    "COHERENCE_SOURCE_SHA": sha,
    "COHERENCE_FORM_SHA": "${FORM_SOURCE_SHA}",
}
out = []
seen = set()
for line in lines:
    if "=" not in line:
        out.append(line)
        continue
    key, value = line.split("=", 1)
    if key in keys:
        out.append(f"{key}={keys[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in keys.items():
    if key not in seen:
        out.append(f"{key}={value}")
env_path.write_text("\n".join(out) + "\n")
PY

python3 - <<PY
import json
import os
from pathlib import Path

sha = "${TARGET_SHA}"
config_path = Path("${REPO_DIR}/api/config/api.json")
config = json.loads(config_path.read_text())
config["deployed_sha"] = sha
web = config.setdefault("web", {})
web["deployed_sha"] = sha
web["updated_at"] = sha
tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
tmp_path.write_text(json.dumps(config, indent=2) + "\n")
tmp_path.replace(config_path)

# Production loads this higher-precedence file inside the API container.  Keep
# the live release identity file-backed and atomic; environment SHA stamps are
# compatibility metadata only and are never the observer's authority.
runtime_path = Path("/root/.coherence-network/config.json")
runtime_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
runtime = json.loads(runtime_path.read_text()) if runtime_path.exists() else {}
runtime["deployed_sha"] = sha
runtime.setdefault("web", {})["deployed_sha"] = sha
runtime["web"]["updated_at"] = sha
runtime.setdefault("deployment_observer", {})["enabled"] = True
# The native release-gate route reads only the production runtime config.
# Seed the public GitHub API origin while preserving any non-empty
# operator-provided override and all credential fields already held there.
# Runtime files may carry null placeholders, so normalize that shape before
# assigning the default instead of relying on setdefault alone.
github = runtime.get("github")
if not isinstance(github, dict):
    github = {}
    runtime["github"] = github
api_base = github.get("api_base")
if not isinstance(api_base, str) or not api_base.strip():
    github["api_base"] = "https://api.github.com"
runtime_tmp = runtime_path.with_name(f".{runtime_path.name}.{os.getpid()}.tmp")
fd = os.open(runtime_tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    payload = (json.dumps(runtime, indent=2, sort_keys=True) + "\n").encode()
    os.write(fd, payload)
    os.fsync(fd)
finally:
    os.close(fd)
os.replace(runtime_tmp, runtime_path)
os.chmod(runtime_path, 0o600)
directory_fd = os.open(runtime_path.parent, os.O_RDONLY)
try:
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
PY

cd "$COMPOSE_ROOT"

# Sync the Dockerfile.api from the repo into the compose root. The api
# image is built with form-kernel-rust baked in at /app/bin/ so transmuted
# endpoints (/api/utils/coherence_weight, ...) shell into the native
# binary instead of falling back to inline Python. The build context for
# the api service stays the repo dir; only the Dockerfile path is sourced
# from the repo so the compose root can keep referencing it as
# `dockerfile: Dockerfile.api` without manual VPS upkeep.
if [[ -f "$REPO_DIR/Dockerfile.api" ]]; then
  if ! cmp -s "$REPO_DIR/Dockerfile.api" "$COMPOSE_ROOT/Dockerfile.api" 2>/dev/null; then
    log "Dockerfile.api: syncing repo -> compose root"
    cp "$REPO_DIR/Dockerfile.api" "$COMPOSE_ROOT/Dockerfile.api"
  fi
else
  log "Dockerfile.api: not present in repo (legacy image path in use)"
fi

# Bump the compose build-context SHAs to TARGET before building. Each service's
# build context is a pinned GitHub URL (context: ...Coherence-Network.git#<sha>
# [:subdir]); `docker compose build` fetches THAT commit, ignoring the local
# repo we just `git reset --hard`'d to TARGET. Without this rewrite every
# rebuild builds the OLD pinned commit while .env DEPLOYED_SHA and /api/health
# report TARGET — the silent stale-code trap that stranded the household router
# and the /hati-suci route on a day-old image (build logged "success", code was
# a day behind, post-deploy verify passed because it reads the env stamp, not
# the actual code). Rewrite every pinned context (api, web, pulse, ...) so the
# build uses the code we are actually deploying. The `:subdir` suffix
# (e.g. #<sha>:pulse) is preserved — only the 7-40 hex SHA after `.git#`
# is replaced.
if grep -qE 'Coherence-Network\.git#[0-9a-f]{7,40}' "$COMPOSE_ROOT/docker-compose.yml"; then
  sed -i -E "s|(Coherence-Network\.git#)[0-9a-f]{7,40}|\1${TARGET_SHA}|g" "$COMPOSE_ROOT/docker-compose.yml"
  log "compose build contexts bumped to ${TARGET_SHA:0:12}"
else
  log "compose build contexts: no pinned github SHA found (local-context build?) — skipped"
fi

# The runtime config stays on the existing read-only parent bind. Grounding
# state is intentionally narrower: four root-owned host directories become
# writable nested binds, so no code can rewrite config or unrelated host state.
GROUNDING_STATE_ROOT="/root/.coherence-network/runtime"
GROUNDING_TARGET_ROOT="/root/.coherence-network"
install -d -m 0700 \
  "$GROUNDING_STATE_ROOT/rag-index" \
  "$GROUNDING_STATE_ROOT/rag-requests" \
  "$GROUNDING_STATE_ROOT/attestation" \
  "$GROUNDING_STATE_ROOT/api-queries"
# The compose service also bind-mounts GROUNDING_TARGET_ROOT read-only. That
# parent mount hides the image's pre-created directories, so runc can only
# attach the four narrower writable binds when their target directories exist
# in the host parent before container creation.
install -d -m 0700 \
  "$GROUNDING_TARGET_ROOT/rag-index" \
  "$GROUNDING_TARGET_ROOT/rag-requests" \
  "$GROUNDING_TARGET_ROOT/attestation" \
  "$GROUNDING_TARGET_ROOT/api-queries"
chown -R root:root "$GROUNDING_STATE_ROOT"

# The image itself carries immutable parent/form source labels.  Compose must
# pass both reviewed commit IDs into every API build, including later `up
# --build` canaries; relying on the container environment would only self-stamp
# runtime claims after the image had already been built.
python3 - "$COMPOSE_ROOT/docker-compose.yml" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8").splitlines()

def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))

api_index = next(
    (i for i, line in enumerate(lines) if line.strip() == "api:" and indent(line) > 0),
    None,
)
if api_index is None:
    raise SystemExit("compose API service missing")
api_indent = indent(lines[api_index])
api_end = next(
    (
        i
        for i in range(api_index + 1, len(lines))
        if lines[i].strip() and indent(lines[i]) <= api_indent
    ),
    len(lines),
)
build_index = next(
    (
        i
        for i in range(api_index + 1, api_end)
        if lines[i].strip() == "build:"
    ),
    None,
)
if build_index is None:
    raise SystemExit("compose API build mapping missing")
build_indent = indent(lines[build_index])
build_end = next(
    (
        i
        for i in range(build_index + 1, api_end)
        if lines[i].strip() and indent(lines[i]) <= build_indent
    ),
    api_end,
)
args_index = next(
    (
        i
        for i in range(build_index + 1, build_end)
        if lines[i].strip() == "args:"
    ),
    None,
)
values = {
    "COHERENCE_SOURCE_SHA": "${COHERENCE_SOURCE_SHA}",
    "COHERENCE_FORM_SHA": "${COHERENCE_FORM_SHA}",
}
if args_index is None:
    child = " " * (build_indent + 2)
    grandchild = " " * (build_indent + 4)
    insertion = [f"{child}args:"] + [
        f'{grandchild}{key}: "${{{key}}}"' for key in values
    ]
    lines[build_end:build_end] = insertion
else:
    args_indent = indent(lines[args_index])
    args_end = next(
        (
            i
            for i in range(args_index + 1, build_end)
            if lines[i].strip() and indent(lines[i]) <= args_indent
        ),
        build_end,
    )
    block = lines[args_index + 1 : args_end]
    list_style = any(line.strip().startswith("-") for line in block if line.strip())
    kept = [
        line
        for line in block
        if not any(key in line for key in values)
    ]
    child = " " * (args_indent + 2)
    if list_style:
        additions = [f'{child}- {key}=${{{key}}}' for key in values]
    else:
        additions = [f'{child}{key}: "${{{key}}}"' for key in values]
    lines[args_index + 1 : args_end] = kept + additions

# A read-only /root/.coherence-network parent mount protects config. Add only
# the exact writable runtime surfaces as nested bind mounts; Docker gives the
# more-specific child mount precedence over the read-only parent.
api_index = next(
    i for i, line in enumerate(lines)
    if line.strip() == "api:" and indent(line) > 0
)
api_indent = indent(lines[api_index])
api_end = next(
    (
        i for i in range(api_index + 1, len(lines))
        if lines[i].strip() and indent(lines[i]) <= api_indent
    ),
    len(lines),
)
volumes_index = next(
    (
        i for i in range(api_index + 1, api_end)
        if lines[i].strip() == "volumes:"
    ),
    None,
)
mounts = [
    "/root/.coherence-network/runtime/rag-index:/root/.coherence-network/rag-index:rw",
    "/root/.coherence-network/runtime/rag-requests:/root/.coherence-network/rag-requests:rw",
    "/root/.coherence-network/runtime/attestation:/root/.coherence-network/attestation:rw",
    "/root/.coherence-network/runtime/api-queries:/root/.coherence-network/api-queries:rw",
]
targets = tuple(item.split(":", 2)[1] for item in mounts)
if volumes_index is None:
    child = " " * (api_indent + 2)
    grandchild = " " * (api_indent + 4)
    lines[api_end:api_end] = [f"{child}volumes:"] + [
        f'{grandchild}- "{mount}"' for mount in mounts
    ]
else:
    volumes_indent = indent(lines[volumes_index])
    volumes_end = next(
        (
            i for i in range(volumes_index + 1, api_end)
            if lines[i].strip() and indent(lines[i]) <= volumes_indent
        ),
        api_end,
    )
    block = lines[volumes_index + 1 : volumes_end]
    first_child = next((line.strip() for line in block if line.strip()), "-")
    if not first_child.startswith("-"):
        raise SystemExit("compose API volumes must use list syntax")
    kept = [line for line in block if not any(target in line for target in targets)]
    child = " " * (volumes_indent + 2)
    lines[volumes_index + 1 : volumes_end] = kept + [
        f'{child}- "{mount}"' for mount in mounts
    ]
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

compose_source_sha="$(docker compose -f "$COMPOSE_ROOT/docker-compose.yml" config --format json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["api"]["build"]["args"]["COHERENCE_SOURCE_SHA"])')"
compose_form_sha="$(docker compose -f "$COMPOSE_ROOT/docker-compose.yml" config --format json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["api"]["build"]["args"]["COHERENCE_FORM_SHA"])')"
if [[ "$compose_source_sha" != "$TARGET_SHA" || "$compose_form_sha" != "$FORM_SOURCE_SHA" ]]; then
  log "FATAL: compose API build provenance args do not match target/form commits"
  exit 1
fi
log "compose API provenance: parent=${TARGET_SHA:0:12} form=${FORM_SOURCE_SHA:0:12}"
docker compose -f "$COMPOSE_ROOT/docker-compose.yml" config --format json \
  | python3 -c '
import json, sys
service = json.load(sys.stdin)["services"]["api"]
volumes = {item["target"]: item for item in service.get("volumes", [])}
expected = {
    "/root/.coherence-network/rag-index",
    "/root/.coherence-network/rag-requests",
    "/root/.coherence-network/attestation",
    "/root/.coherence-network/api-queries",
}
missing = sorted(target for target in expected if target not in volumes)
readonly = sorted(target for target in expected if volumes.get(target, {}).get("read_only"))
if missing or readonly:
    raise SystemExit(f"grounding state bind contract failed missing={missing} readonly={readonly}")
'
log "compose API grounding state: four narrow writable binds verified"
# Select the additional services whose source changed. The deployment body
# always adds API to this set below because the observer requires an image
# whose immutable revision label equals TARGET_SHA; web and pulse remain
# path-scoped to avoid unrelated rebuilds.
#
# Conservative fallback: anything outside the recognized roots rebuilds all
# three services. We narrow only when every changed path is accounted for.
services_to_rebuild() {
  local from="$1" to="$2"
  if [[ -z "$from" || -z "$to" || "$from" == "$to" ]]; then
    echo "api web pulse"
    return 0
  fi
  local changed
  changed="$(changed_paths_between "$from" "$to" 2>/dev/null || true)"
  if [[ -z "$changed" ]]; then
    echo "api web pulse"
    return 0
  fi
  local need_api=0 need_web=0 need_pulse=0
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    case "$path" in
      Dockerfile.api)   need_api=1 ;;
      Dockerfile.web)   need_web=1 ;;
      api/*)           need_api=1 ;;
      web/*)           need_web=1 ;;
      pulse/*)         need_pulse=1 ;;
      form)                     need_api=1 ;;
      form/form-stdlib/*)      need_api=1 ;;
      form/form-kernel-rust/*) need_api=1 ;;
      # scripts/ is mounted as content but also copied into the api image
      # at build time for the substrate ingester. Rebuild api when they change.
      scripts/*.py)    need_api=1 ;;
      scripts/*.sh)    need_api=1 ;;
      # Anything else (deploy/, docs/, README.md, .github/, etc.) does not
      # require a service rebuild. The static-only path handled docs above;
      # if we're here, at least one change wasn't static-only — but it still
      # may not touch a service tree (e.g. deploy/hostinger/auto-deploy.sh
      # itself, which is synced separately by the workflow).
      *) ;;
    esac
  done <<< "$changed"
  local out=()
  (( need_api ))   && out+=("api")
  (( need_web ))   && out+=("web")
  (( need_pulse )) && out+=("pulse")
  if [[ ${#out[@]} -eq 0 ]]; then
    # No service-touching changes detected — but we entered the rebuild branch
    # because static-only said "no." Be conservative: rebuild all so we don't
    # silently skip an intentional rebuild trigger we didn't classify.
    echo "api web pulse"
    return 0
  fi
  echo "${out[*]}"
}

compose_service_state() {
  local service="$1"
  docker compose ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$service" '$1==s {print $2; exit}'
}

wait_for_compose_service_running() {
  local service="$1"
  local timeout_seconds="${2:-180}"
  local deadline=$(( $(date +%s) + timeout_seconds ))
  local state
  while (( $(date +%s) < deadline )); do
    state="$(compose_service_state "$service")"
    if [[ "$state" == "running" ]]; then
      return 0
    fi
    sleep 3
  done
  return 1
}

recreate_orphans_for_service() {
  local service="$1"
  docker ps -a --format '{{.Names}}' | grep -E "^[0-9a-f]{6,}_coherence-network-${service}-1$" || true
}

containers_for_service() {
  local service="$1"
  docker ps -a --format '{{.Names}}' | grep -E "(^|_)coherence-network-${service}-1$" || true
}

wait_for_recreate_orphans_gone() {
  local service="$1"
  local timeout_seconds="${2:-60}"
  local deadline=$(( $(date +%s) + timeout_seconds ))
  local orphans
  while (( $(date +%s) < deadline )); do
    orphans="$(recreate_orphans_for_service "$service")"
    if [[ -z "$orphans" ]]; then
      return 0
    fi
    log "waiting for recreate orphan removal for ${service}: $(echo "$orphans" | tr '\n' ' ')"
    sleep 2
  done

  orphans="$(recreate_orphans_for_service "$service")"
  if [[ -n "$orphans" ]]; then
    log "clearing recreate orphans still present for ${service}: $(echo "$orphans" | tr '\n' ' ')"
    echo "$orphans" | xargs -r docker rm -f >/dev/null 2>&1 || true
  fi
}

wait_for_service_container_names_gone() {
  local service="$1"
  local timeout_seconds="${2:-60}"
  local deadline=$(( $(date +%s) + timeout_seconds ))
  local names
  while (( $(date +%s) < deadline )); do
    names="$(containers_for_service "$service")"
    if [[ -z "$names" ]]; then
      return 0
    fi
    log "waiting for container name release for ${service}: $(echo "$names" | tr '\n' ' ')"
    sleep 2
  done

  names="$(containers_for_service "$service")"
  if [[ -n "$names" ]]; then
    log "clearing container names still present for ${service}: $(echo "$names" | tr '\n' ' ')"
    echo "$names" | xargs -r docker rm -f >/dev/null 2>&1 || true
  fi
}

wait_for_rebuild_recreate_orphans_gone() {
  local service
  for service in "$@"; do
    wait_for_recreate_orphans_gone "$service"
  done
}

# Pick the comparison base: prefer what's ACTUALLY RUNNING in the api
# container over what the repo claims is its HEAD. The repo's OLD_SHA
# gets advanced by `git reset --hard` on every deploy, but if a prior
# rebuild stalled silently the container is still at an older SHA.
# Detecting changes from OLD_SHA in that case sees an empty/static-only
# diff and skips rebuild — pinning the container at the old SHA forever.
# Using RUNNING_SHA as the comparison base means: change-detection asks
# what the CONTAINER is missing, not what the filesystem is missing.
DIFF_BASE="$OLD_SHA"
if [[ -n "$RUNNING_SHA" ]] && git cat-file -e "${RUNNING_SHA}^{commit}" 2>/dev/null; then
  if [[ "$RUNNING_SHA" != "$OLD_SHA" ]]; then
    log "Diff base: using RUNNING_SHA=${RUNNING_SHA:0:12} (container) instead of OLD_SHA=${OLD_SHA:0:12} (repo) — the repo may have advanced past a stalled rebuild"
  fi
  DIFF_BASE="$RUNNING_SHA"
fi

# The independent observer binds the target SHA to immutable image labels and
# reproduces both native carriers from that exact source.  Therefore every
# target commit rebuilds the API image; a new SHA can never be injected into an
# old image through environment/config recreation.
REBUILD_SERVICES="$(services_to_rebuild "$DIFF_BASE" "$TARGET_SHA")"
case " ${REBUILD_SERVICES} " in
  *" api "*) ;;
  *) REBUILD_SERVICES="api ${REBUILD_SERVICES}" ;;
esac
if [[ "$HATI_WEB_HOSTS_CHANGED" == "1" ]]; then
  case " ${REBUILD_SERVICES} " in
    *" web "*) ;;
    *)
      REBUILD_SERVICES="${REBUILD_SERVICES} web"
      log "Hati web hosts: forcing web service update so Traefik receives the new host labels"
      ;;
  esac
fi
log "Rebuild scope: ${REBUILD_SERVICES} (changed paths -> services, diff_base=${DIFF_BASE:0:12})"

build_started="$(date +%s)"
log "docker compose build ${REBUILD_SERVICES}"
# shellcheck disable=SC2086 -- intentional word-splitting on service list
docker compose build ${REBUILD_SERVICES} 2>&1 | tee -a "$LOG_FILE"
build_ended="$(date +%s)"
build_elapsed=$((build_ended - build_started))
log "TIMING: docker compose build took ${build_elapsed}s"

up_started="$(date +%s)"
# --wait holds the command until the new containers report healthy (per
# their HEALTHCHECK), so we never declare "deployed" while Traefik is
# still routing to a half-warm container. --wait-timeout 180s matches the
# wait_for_running deadline used below for the legacy state-only check.
# --force-recreate guarantees a fresh container even when the image hash
# didn't change — a build that's an all-cache-hit produces the same image,
# and without --force-recreate compose would skip the restart, leaving the
# running container's env (GIT_COMMIT_SHA, DEPLOYED_SHA) at the old values.
# That was the silent-skip pattern that pinned production at 4183d306 for
# 5h+; we never again trust compose's "no config change detected" verdict.
# If --wait is unsupported by the installed compose version, fall back to
# plain `up -d --force-recreate`.
# Clear leftover hash-prefixed containers from a prior interrupted recreate
# (e.g. `998358986afb_coherence-network-api-1`). --force-recreate builds a
# temp-named container then renames it onto the canonical name; if an earlier
# run died mid-swap, the orphan keeps the name and every later recreate fails
# with "container name ... already in use". Removing only the hash-prefixed
# strays leaves the live container running — no downtime in the common case.
orphans="$(docker ps -a --format '{{.Names}}' | grep -E '^[0-9a-f]{6,}_coherence-network-[a-z0-9-]+-1$' || true)"
if [[ -n "$orphans" ]]; then
  log "clearing recreate orphans: $(echo "$orphans" | tr '\n' ' ')"
  echo "$orphans" | xargs -r docker rm -f >/dev/null 2>&1 || true
fi
# Docker may report async removal-in-progress for the hash-prefixed
# recreate container. Wait until names are actually released before asking
# compose to start the same service again.
# shellcheck disable=SC2086 -- intentional word-splitting on service list
wait_for_rebuild_recreate_orphans_gone ${REBUILD_SERVICES}
log "docker compose up -d --wait --wait-timeout 180 --force-recreate ${REBUILD_SERVICES}"
# shellcheck disable=SC2086 -- intentional word-splitting on service list
if ! docker compose up -d --wait --wait-timeout 180 --force-recreate ${REBUILD_SERVICES} 2>&1 | tee -a "$LOG_FILE"; then
  log "docker compose up --wait failed or unsupported; falling back to plain up -d --force-recreate"
  # shellcheck disable=SC2086
  if ! docker compose up -d --force-recreate ${REBUILD_SERVICES} 2>&1 | tee -a "$LOG_FILE"; then
    # Last resort for the name-swap conflict: stop+remove the services
    # outright (compose-aware), then bring them up clean. Costs a few seconds
    # of downtime per service but never wedges on a held name. This is the
    # manual recovery (`compose rm -fs` + `up -d`) that resolved it by hand.
    log "force-recreate still conflicted; stop+remove then clean up -d"
    # shellcheck disable=SC2086
    docker compose rm -fsv ${REBUILD_SERVICES} 2>&1 | tee -a "$LOG_FILE" || true
    # shellcheck disable=SC2086 -- intentional word-splitting on service list
    wait_for_rebuild_recreate_orphans_gone ${REBUILD_SERVICES}
    # shellcheck disable=SC2086
    docker compose up -d ${REBUILD_SERVICES} 2>&1 | tee -a "$LOG_FILE"
  fi
fi
up_ended="$(date +%s)"
up_elapsed=$((up_ended - up_started))
log "TIMING: docker compose up took ${up_elapsed}s"

# Post-condition: every targeted service MUST end up running. The recreate
# dance — and its rm-then-up recovery — can silently leave a service down.
# That took the whole site offline once: api came back, web + pulse did not,
# and nothing noticed for ~an hour. Never declare a deploy done with a
# service missing; clear orphans for it, recreate, and fail loudly if it
# still won't start. This only touches services that are NOT running, so it
# can't disturb a healthy one.
# shellcheck disable=SC2086 -- intentional word-splitting on service list
for svc in ${REBUILD_SERVICES}; do
  if ! docker ps --format '{{.Names}}' | grep -qx "coherence-network-${svc}-1"; then
    log "post-deploy: ${svc} is NOT running — clearing orphans and forcing a clean recreate"
    docker ps -a --format '{{.Names}}' | grep -E "(^|_)coherence-network-${svc}-1$" | xargs -r docker rm -f >/dev/null 2>&1 || true
    wait_for_recreate_orphans_gone "$svc"
    docker compose up -d "${svc}" 2>&1 | tee -a "$LOG_FILE" || true
    sleep 3
    if docker ps --format '{{.Names}}' | grep -qx "coherence-network-${svc}-1"; then
      log "post-deploy: ${svc} recovered"
    else
      log "FATAL post-deploy: ${svc} STILL not running after clean recreate — site may be degraded"
    fi
  fi
done


sync_field_docs() {
  if [[ ! -d "$REPO_DIR/docs/field" ]]; then
    log "field docs: no docs/field directory found (skipped)"
    return 0
  fi

  if ! wait_for_compose_service_running api 180; then
    log "FATAL field docs: api container did not reach running before docs sync"
    return 1
  fi

  # The api container may still be settling right after a force-recreate (exec races the fresh
  # container and its exit code would fail a deploy whose site is already up — seen on f51a968).
  # Retry briefly; fail honestly only if the sync truly cannot land.
  local target_parent attempt ok
  for target_parent in /app/docs /app/api/docs; do
    log "field docs: syncing docs/field to api:${target_parent}/field"
    ok=0
    for attempt in 1 2 3; do
      if docker compose exec -T api sh -lc "mkdir -p '${target_parent}' && rm -rf '${target_parent}/field'" \
           2>&1 | tee -a "$LOG_FILE" \
         && docker compose cp "$REPO_DIR/docs/field" "api:${target_parent}/field" \
           2>&1 | tee -a "$LOG_FILE"; then
        ok=1
        break
      fi
      log "field docs: attempt ${attempt} failed (container may still be settling); retrying in 5s"
      sleep 5
    done
    if [[ "$ok" != 1 ]]; then
      log "FATAL field docs: sync to ${target_parent} failed after 3 attempts"
      return 1
    fi
  done
}

sync_field_docs

sync_form_stdlib() {
  if [[ ! -d "$REPO_DIR/form/form-stdlib" ]]; then
    log "form stdlib: no form/form-stdlib directory found (skipped)"
    return 0
  fi

  local changed
  changed="$(changed_paths_between "$DIFF_BASE" "$TARGET_SHA" 2>/dev/null || true)"
  if ! grep -Eq '^(form$|form/form-stdlib/)' <<< "$changed"; then
    log "form stdlib: no changes"
    return 0
  fi

  log "form stdlib: syncing form/form-stdlib to api:/app/form/form-stdlib"
  docker compose exec -T api sh -lc 'mkdir -p /app/form && rm -rf /app/form/form-stdlib' \
    2>&1 | tee -a "$LOG_FILE" || true
  docker compose cp "$REPO_DIR/form/form-stdlib" api:/app/form/form-stdlib \
    2>&1 | tee -a "$LOG_FILE"
}

sync_form_stdlib

# Substrate auto-ingest. The coherence-substrate (content-addressed
# numeric lattice) lives in the api's database. Each deploy syncs the
# source-of-truth content (specs, ideas, vision-kb concepts, presences)
# into the container and re-runs the ingester. Re-ingestion is
# idempotent — content-addressed Blueprint NodeIDs hash-match existing
# cells. Memory cells live outside the repo (in ~/.claude/) and are
# skipped automatically. Grounding is a deployment contract: an incomplete
# substrate or path-only RAG index fails the deploy instead of shipping a
# healthy-looking service whose core cannot answer from its own body.
# Runs AFTER wait_for_running api so the DB connection is stable.
sync_substrate_content() {
  log "substrate: syncing content + scripts into api container"
  docker compose exec -T api sh -lc 'rm -rf /app/specs /app/ideas /app/scripts /app/docs/vision-kb /app/docs/presences /app/docs/lineage' \
    2>&1 | tee -a "$LOG_FILE" || true
  docker compose cp "$REPO_DIR/scripts" api:/app/scripts 2>&1 | tee -a "$LOG_FILE"
  docker compose cp "$REPO_DIR/specs" api:/app/specs 2>&1 | tee -a "$LOG_FILE"
  docker compose cp "$REPO_DIR/ideas" api:/app/ideas 2>&1 | tee -a "$LOG_FILE"
  if [[ -d "$REPO_DIR/docs/vision-kb" ]]; then
    docker compose cp "$REPO_DIR/docs/vision-kb" api:/app/docs/vision-kb 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -d "$REPO_DIR/docs/presences" ]]; then
    docker compose cp "$REPO_DIR/docs/presences" api:/app/docs/presences 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -d "$REPO_DIR/docs/lineage" ]]; then
    docker compose cp "$REPO_DIR/docs/lineage" api:/app/docs/lineage 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -d "$REPO_DIR/docs/breath" ]]; then
    docker compose cp "$REPO_DIR/docs/breath" api:/app/docs/breath 2>&1 | tee -a "$LOG_FILE"
  fi
  # Single-file evidence the registry-submissions endpoint reads at import
  # time. Without this copy /app/docs/registry-submissions.json is missing
  # and the endpoint returns items:[] (core_requirement_met:false) even
  # though the file is healthy at the repo root.
  if [[ -f "$REPO_DIR/docs/registry-submissions.json" ]]; then
    docker compose exec -T api sh -lc 'mkdir -p /app/docs' \
      2>&1 | tee -a "$LOG_FILE" || true
    docker compose cp "$REPO_DIR/docs/registry-submissions.json" \
      api:/app/docs/registry-submissions.json 2>&1 | tee -a "$LOG_FILE"
  fi

  # Registry submission assets the validator checks per-item. The body
  # already carries glama.json, server.json, smithery.yaml, pulsemcp.json,
  # the MCP package README, SKILL.md, .cursor/, the root README,
  # and docs/shared/ecosystem-table.md at the repo root. Inside the api
  # container these surfaces live under /app/, where the validator
  # resolves repo-root via parents[2]. Sync them so the live endpoint
  # sees the same readiness the local validator sees.
  docker compose exec -T api sh -lc 'rm -rf /app/mcp-server /app/skills /app/.cursor/skills /app/docs/shared' \
    2>&1 | tee -a "$LOG_FILE" || true
  if [[ -d "$REPO_DIR/mcp-server" ]]; then
    docker compose cp "$REPO_DIR/mcp-server" api:/app/mcp-server 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -d "$REPO_DIR/skills" ]]; then
    docker compose cp "$REPO_DIR/skills" api:/app/skills 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -d "$REPO_DIR/.cursor" ]]; then
    docker compose cp "$REPO_DIR/.cursor" api:/app 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -d "$REPO_DIR/docs/shared" ]]; then
    docker compose cp "$REPO_DIR/docs/shared" api:/app/docs/shared 2>&1 | tee -a "$LOG_FILE"
  fi
  if [[ -f "$REPO_DIR/README.md" ]]; then
    docker compose cp "$REPO_DIR/README.md" api:/app/README.md 2>&1 | tee -a "$LOG_FILE"
  fi
  # The registry inventory references the MCP entry point at its repo-
  # relative path (api/mcp_server.py). Inside the container the file
  # lives at /app/mcp_server.py because the api directory is the
  # container root. Mirror it under /app/api/ so the validator's
  # source_paths check resolves the same in both layouts.
  if [[ -f "$REPO_DIR/api/mcp_server.py" ]]; then
    docker compose exec -T api sh -lc 'mkdir -p /app/api' \
      2>&1 | tee -a "$LOG_FILE" || true
    docker compose cp "$REPO_DIR/api/mcp_server.py" api:/app/api/mcp_server.py \
      2>&1 | tee -a "$LOG_FILE"
  fi
}

run_substrate_ingest() {
  # If we can compute the changed-files set since the last deployed SHA,
  # ingest ONLY those files instead of re-ingesting all 481+. The
  # substrate's cell-intern is already content-addressed (same hash →
  # same NodeID, no new row), but the file read + parse + encode runs
  # for every file in --all mode regardless. Per-file ingest with the
  # git-changed set turns this from minutes-to-tens-of-minutes into
  # seconds when content hasn't changed in the ingestable domains.
  #
  # Fall back to --all when:
  #   - OLD_SHA unknown (cold start)
  #   - OLD_SHA == TARGET_SHA but rebuild was requested (running API at
  #     wrong SHA path)
  #   - git diff fails for any reason
  local from="$1" to="$2"
  local started ended elapsed all_changed full_refresh_reason=""
  started="$(date +%s)"

  if [[ -z "$from" || "$from" == "$to" ]]; then
    full_refresh_reason="SHAs unknown or equal"
  elif ! all_changed="$(changed_paths_between "$from" "$to" 2>/dev/null)"; then
    full_refresh_reason="changed-path comparison unavailable"
  elif grep -Fxq 'form/.gitlink-diff-unavailable' <<< "$all_changed"; then
    full_refresh_reason="form gitlink commits unavailable"
  fi

  if [[ -n "$full_refresh_reason" ]]; then
    log "substrate: ${full_refresh_reason} — bootstrapping the complete grounded body"
    set +e
    # A measured cold SQLite bootstrap of the complete 1,546-source corpus can
    # exceed twenty minutes while structured concept CTORs are interned. Give
    # the complete rebuild a full hour; a timeout must never manufacture a
    # partial "ready" body.
    run_with_timeout "${SUBSTRATE_INGEST_ALL_TIMEOUT_SECONDS:-3600}" \
      docker compose exec -T api sh -lc \
        'cd /app && python3 scripts/coh_substrate.py bootstrap && bash scripts/ensure_form_cli_native.sh && python3 scripts/form_cli_rag.py heal' \
      2>&1 | tee -a "$LOG_FILE"
    local rc=$?
    set -e
    ended="$(date +%s)"
    elapsed=$((ended - started))
    log "substrate: complete bootstrap took ${elapsed}s (rc=$rc)"
    if [[ "$rc" -ne 0 ]]; then
      log "FAIL: grounded substrate/RAG bootstrap returned $rc"
    fi
    return "$rc"
  fi

  # Ingestable tissue: the .md content domains PLUS the substrate's own
  # shape-files (docs/coherence-substrate/*.form) and stdlib recipes
  # (form/form-stdlib/**/*.fk). The latter two land as ARTIFACT cells so
  # form-first attribution can resolve their NodeIDs from the live lattice
  # instead of from memory. They reach the substrate only through
  # ingest-paths (the `ingest`/`ingest --all` commands skip non-.md), so
  # the per-file loop below dispatches every path through ingest-paths.
  local changed
  changed="$(printf '%s\n' "$all_changed" \
              | grep -E '^(specs|ideas|docs/vision-kb|docs/presences|docs/lineage|docs/breath)/.*\.md$|^docs/coherence-substrate/.*\.form$|^docs/shared/.*\.md$|^form/form-stdlib/.*\.fk$' \
              | while IFS= read -r path; do
                  [[ -f "$REPO_DIR/$path" ]] && printf '%s\n' "$path"
                done \
              || true)"
  if [[ -z "$changed" ]]; then
    ended="$(date +%s)"
    elapsed=$((ended - started))
    log "substrate: no ingestable files changed in ${from:0:12}..${to:0:12} — skipped (${elapsed}s)"
    return 0
  fi

  local count
  count="$(printf '%s\n' "$changed" | grep -c .)"
  log "substrate: ingesting $count changed files (not --all)"

  set +e
  local rc=0
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    # ingest-paths (not `ingest`) so .form/.fk land as ARTIFACT cells and
    # .md still routes to its domain ingester. Structured CTOR is the
    # default; the 300s ceiling covers a concept's word-cell interning
    # against prod Postgres (120s dropped lc-cognitive-sovereignty).
    run_with_timeout "${SUBSTRATE_INGEST_FILE_TIMEOUT_SECONDS:-300}" \
      docker compose exec -T api sh -lc "cd /app && python3 scripts/coh_substrate.py ingest-paths '/app/$path'" \
      2>&1 | tee -a "$LOG_FILE"
    local file_rc=$?
    if [[ "$file_rc" -ne 0 ]]; then
      log "substrate: ingest failed for $path (rc=$file_rc) — continuing"
      rc=$file_rc
    fi
  done <<< "$changed"
  set -e

  ended="$(date +%s)"
  elapsed=$((ended - started))
  if [[ "$rc" -eq 0 ]] && grep -Eq \
      '^(specs/.*\.md|docs/vision-kb/concepts/.*\.md|docs/coherence-substrate/.*\.form|docs/shared/.*\.md|form/form-stdlib/.*\.fk)$' \
      <<< "$changed"; then
    run_with_timeout "${SUBSTRATE_RAG_HEAL_TIMEOUT_SECONDS:-300}" \
      docker compose exec -T api sh -lc \
        'cd /app && bash scripts/ensure_form_cli_native.sh && python3 scripts/form_cli_rag.py heal' \
      2>&1 | tee -a "$LOG_FILE"
    rc=$?
  fi

  log "substrate: ingest + NodeID RAG heal of $count files took ${elapsed}s (final rc=$rc)"
  if [[ "$rc" -ne 0 ]]; then
    log "FAIL: incremental grounded substrate/RAG refresh returned $rc"
  fi
  return "$rc"
}

# Wait for both containers to reach the "running" state in docker compose.
# The deeper health check is left to the workflow's Verify Public Deployment
# step, which curls the real public domain through the full request path
# (Traefik, Cloudflare, TLS). That sensor sees the organism the way every
# caller sees it and is the truth. Anything we could check here locally is
# a thinner, redundant version of the same question, and the previous
# `docker compose exec api curl` shape caught a false failure when curl
# happened not to be present inside the api container image.
wait_for_running() {
  local service="$1"
  wait_for_compose_service_running "$service" 180
}

ensure_kernel_router_canary() {
  if [[ ! -f "$KERNEL_CANARY_COMPOSE_FILE" ]]; then
    log "kernel-router canary: overlay missing at $KERNEL_CANARY_COMPOSE_FILE (skipped)"
    return 0
  fi

  log "kernel-router canary: ensuring bounded mutable native production-manifest service and BML front-door path service"
  local compose_args=(-f "$COMPOSE_ROOT/docker-compose.yml" -f "$KERNEL_CANARY_COMPOSE_FILE")
  local canary_services=(kernel-router kernel-router-bml-front-door)
  local started ended elapsed
  started="$(date +%s)"

  local service stale
  for service in "${canary_services[@]}"; do
    stale="$(containers_for_service "$service")"
    if [[ -n "$stale" ]]; then
      log "kernel-router canary: clearing stale containers for ${service}: $(echo "$stale" | tr '\n' ' ')"
      echo "$stale" | xargs -r docker rm -f >/dev/null 2>&1 || true
      wait_for_service_container_names_gone "$service"
    fi
  done

  set +e
  docker compose "${compose_args[@]}" up -d --build --no-deps --wait --wait-timeout 180 "${canary_services[@]}" \
    2>&1 | tee -a "$LOG_FILE"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 ]]; then
    log "kernel-router canary: compose up --wait failed; falling back to plain up -d --build --no-deps --force-recreate"
    if ! docker compose "${compose_args[@]}" up -d --build --no-deps --force-recreate "${canary_services[@]}" 2>&1 | tee -a "$LOG_FILE"; then
      log "kernel-router canary: force-recreate still conflicted; stop+remove then clean up -d"
      docker compose "${compose_args[@]}" rm -fsv "${canary_services[@]}" 2>&1 | tee -a "$LOG_FILE" || true
      for service in "${canary_services[@]}"; do
        containers_for_service "$service" | xargs -r docker rm -f >/dev/null 2>&1 || true
        wait_for_service_container_names_gone "$service"
      done
      docker compose "${compose_args[@]}" up -d --build --no-deps "${canary_services[@]}" 2>&1 | tee -a "$LOG_FILE"
    fi
  fi

  local deadline state listener_ready
  for service in "${canary_services[@]}"; do
    deadline=$(( $(date +%s) + 180 ))
    state=""
    while (( $(date +%s) < deadline )); do
      state="$(docker compose "${compose_args[@]}" ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v service="$service" '$1==service {print $2}')"
      if [[ "$state" == "running" ]]; then
        break
      fi
      sleep 3
    done
    if [[ "$state" != "running" ]]; then
      log "FAIL: $service did not reach running state within 180s"
      exit 1
    fi
  done

  for service in "${canary_services[@]}"; do
    # The production-manifest kernel-router has already passed compose/Docker
    # health above, and the public-gate/default mutation probes below prove its
    # real routed behavior through Traefik. A second local docker-exec curl has
    # repeatedly false-failed while the public canary succeeded after routing
    # settled, so only the BML sibling keeps a local listener probe here.
    if [[ "$service" == "kernel-router" ]]; then
      log "kernel-router canary: ${service} listener covered by Docker health and public mutation probes"
      continue
    fi
    local listener_probe_path="/api/utils/kernel_status"
    local listener_wait_seconds=360
    local listener_curl_timeout_seconds=10
    # Contract marker: $service listener did not accept local HTTP within 360s.
    log "kernel-router canary: waiting for ${service} listener at ${listener_probe_path} (${listener_wait_seconds}s budget)"
    deadline=$(( $(date +%s) + listener_wait_seconds ))
    listener_ready=0
    while (( $(date +%s) < deadline )); do
      if docker compose "${compose_args[@]}" exec -T "$service" sh -lc \
        "curl -fsS --max-time ${listener_curl_timeout_seconds} -o /dev/null http://127.0.0.1:8080${listener_probe_path}" \
        >/dev/null 2>&1; then
        listener_ready=1
        break
      fi
      sleep 3
    done
    if [[ "$listener_ready" != "1" ]]; then
      log "FAIL: $service listener did not accept local HTTP at ${listener_probe_path} within ${listener_wait_seconds}s"
      docker compose "${compose_args[@]}" ps 2>&1 | tee -a "$LOG_FILE" || true
      docker compose "${compose_args[@]}" logs --tail=120 "$service" 2>&1 | tee -a "$LOG_FILE" || true
      exit 1
    fi
  done

  local canary_id="idea-public-canary-local-$(date +%s)"
  local payload
  local probe_ok
  payload="$(printf '{"id":"%s","name":"Public Canary Local","description":"header-gated canary","manifestation_status":"partial"}' "$canary_id")"
  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router sh -lc \
      "curl -fsS -D /tmp/kernel-canary.headers -o /tmp/kernel-canary.body \
        -X POST http://127.0.0.1:8080/api/ideas \
        -H 'Content-Type: application/json' \
        -H 'X-Form-Native-Public-Gate: 1' \
        --data '$payload' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/kernel-canary.headers \
        && grep -q '\"decision_receipt\"' /tmp/kernel-canary.body \
        && grep -q '\"native_invitation\"' /tmp/kernel-canary.body \
        && grep -q '\"state\":\"native-invitation-contract\"' /tmp/kernel-canary.body \
        && grep -q '\"native_protocol\":\"Form/BML mutation recipe\"' /tmp/kernel-canary.body \
        && grep -q '\"executes\":true' /tmp/kernel-canary.body \
        && grep -q '\"db_execution\":\"performed-by-http-native-persistence\"' /tmp/kernel-canary.body \
        && grep -q '\"ordinary_traffic_flip_performed\":true' /tmp/kernel-canary.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: kernel-router canary local public-gate probe did not execute native persistence and return native decision receipt"
    exit 1
  fi

  local default_id="idea-native-default-local-$(date +%s)"
  local default_payload
  default_payload="$(printf '{"id":"%s","name":"Native Default Local","description":"no-header native default","manifestation_status":"partial"}' "$default_id")"
  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router sh -lc \
      "curl -fsS -D /tmp/kernel-default.headers -o /tmp/kernel-default.body \
        -X POST http://127.0.0.1:8080/api/ideas \
        -H 'Content-Type: application/json' \
        --data '$default_payload' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/kernel-default.headers \
        && grep -q '\"native_default_invitation\":true' /tmp/kernel-default.body \
        && grep -q '\"native_invitation\"' /tmp/kernel-default.body \
        && grep -q '\"state\":\"native-invitation-contract\"' /tmp/kernel-default.body \
        && grep -q '\"native_protocol\":\"Form/BML mutation recipe\"' /tmp/kernel-default.body \
        && grep -q '\"route_binding\":\"kernel-http-native-default-invitation\"' /tmp/kernel-default.body \
        && grep -q '\"selected_path\":\"implicit-native-invitation\"' /tmp/kernel-default.body \
        && grep -q '\"executes\":true' /tmp/kernel-default.body \
        && grep -q '\"db_execution\":\"performed-by-http-native-persistence\"' /tmp/kernel-default.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: kernel-router canary local no-header native default probe did not execute native persistence"
    exit 1
  fi

  deadline=$(( $(date +%s) + 60 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router sh -lc \
      "curl -sS -D /tmp/kernel-fallback.headers -o /tmp/kernel-fallback.body -w '%{http_code}' \
        -X POST http://127.0.0.1:8080/api/ideas \
        -H 'Content-Type: application/json' \
        -H 'X-Form-Python-Fallback: 1' \
        --data '{}' >/tmp/kernel-fallback.status \
        && grep -qi '^X-Form-Router: fanout-python' /tmp/kernel-fallback.headers" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: kernel-router explicit fallback did not fan out with X-Form-Router: fanout-python"
    exit 1
  fi

  local kernel_image_payload='{"expression":"class KernelCoreSelf { int RequiredPrimitiveCount() [get] { return 8; } int RequiredDispatchCount() [get] { return 15; } int RequiredProofCount() [get] { return 6; } bool Minimal() { return true; } bool Observable() { return true; } bool Executable() { return true; } bool Trustable() { return true; } } class KernelCoreImage {}","grammar":"bml","source_label":"deploy-bml-front-door-canary"}'
  deadline=$(( $(date +%s) + 360 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "printf '%s' '$kernel_image_payload' >/tmp/kernel-image.request.json \
        && curl -fsS --max-time 30 -D /tmp/kernel-image.headers -o /tmp/kernel-image.body \
        -X POST http://127.0.0.1:8080/api/substrate/kernel-image/proposals \
        -H 'Accept: application/json' \
        -H 'Content-Type: application/json' \
        --data-binary @/tmp/kernel-image.request.json \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/kernel-image.headers \
        && grep -q '\"proposal_status\":\"accepted-preview\"' /tmp/kernel-image.body \
        && grep -q '\"handler\":\"api_substrate_kernel_image_proposals\"' /tmp/kernel-image.body \
        && grep -q '\"python_authority\":false' /tmp/kernel-image.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "echo 'kernel-image headers:'; cat /tmp/kernel-image.headers 2>/dev/null || true; \
       echo 'kernel-image body:'; head -c 1200 /tmp/kernel-image.body 2>/dev/null || true; echo" \
      2>&1 | tee -a "$LOG_FILE" || true
    log "FAIL: BML front-door kernel-image route did not return native proposal proof"
    exit 1
  fi

  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "curl -fsS --max-time 10 -D /tmp/inventory-flow.headers -o /tmp/inventory-flow.body \
        'http://127.0.0.1:8080/api/inventory/flow?idea_id=__native_inventory_canary__&list_item_limit=1&runtime_window_seconds=3600' \
        -H 'Accept: application/json' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/inventory-flow.headers \
        && grep -q '\"handler\":\"api_inventory_flow\"' /tmp/inventory-flow.body \
        && grep -q '\"python_authority\":false' /tmp/inventory-flow.body \
        && grep -q '\"items\":\\[\\]' /tmp/inventory-flow.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: BML front-door inventory flow route did not return native inventory proof"
    exit 1
  fi

  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "curl -fsS --max-time 10 -D /tmp/inventory-flow-observe.headers -o /tmp/inventory-flow-observe.body \
        'http://127.0.0.1:8080/api/_form/inventory-flow-observation?idea_id=__native_inventory_canary__&list_item_limit=1&runtime_window_seconds=3600&event_limit=20&warm=1' \
        -H 'Accept: application/json' \
        -H 'X-Form-Observe: 1' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/inventory-flow-observe.headers \
        && grep -q '\"handler\":\"api_inventory_flow_observe\"' /tmp/inventory-flow-observe.body \
        && grep -q '\"observed_handler\":\"api_inventory_flow\"' /tmp/inventory-flow-observe.body \
        && grep -q '\"observed_canary\":true' /tmp/inventory-flow-observe.body \
        && grep -q '\"python_authority\":false' /tmp/inventory-flow-observe.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: BML front-door inventory flow observation route did not return native observation proof"
    exit 1
  fi

  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "curl -fsS --max-time 10 -D /tmp/kernel-status.headers -o /tmp/kernel-status.body \
        'http://127.0.0.1:8080/api/utils/kernel_status' \
        -H 'Accept: application/json' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/kernel-status.headers \
        && grep -qi '^X-Form-Handler: api_kernel_status' /tmp/kernel-status.headers \
        && grep -qi '^X-Form-Python-Authority: false' /tmp/kernel-status.headers \
        && grep -q '\"active\":\"native-kernel\"' /tmp/kernel-status.body \
        && grep -q '\"router\":\"native-kernel\"' /tmp/kernel-status.body \
        && grep -q '\"python_authority\":false' /tmp/kernel-status.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: BML front-door kernel status route did not return native authority proof"
    exit 1
  fi

  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "curl -fsS --max-time 10 -D /tmp/agent-tasks-active.headers -o /tmp/agent-tasks-active.body \
        'http://127.0.0.1:8080/api/agent/tasks/active' \
        -H 'Accept: application/json' \
        && curl -fsS --max-time 10 -D /tmp/agent-tasks-activity.headers -o /tmp/agent-tasks-activity.body \
        'http://127.0.0.1:8080/api/agent/tasks/activity?limit=50&offset=0' \
        -H 'Accept: application/json' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/agent-tasks-active.headers \
        && grep -qi '^X-Form-Handler: api_agent_tasks_active' /tmp/agent-tasks-active.headers \
        && grep -qi '^X-Form-Python-Authority: false' /tmp/agent-tasks-active.headers \
        && test \"\$(tr -d '[:space:]' </tmp/agent-tasks-active.body)\" = '[]' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/agent-tasks-activity.headers \
        && grep -qi '^X-Form-Handler: api_agent_tasks_activity' /tmp/agent-tasks-activity.headers \
        && grep -qi '^X-Form-Python-Authority: false' /tmp/agent-tasks-activity.headers \
        && grep -q '\"items\":\\[\\]' /tmp/agent-tasks-activity.body \
        && grep -q '\"total\":0' /tmp/agent-tasks-activity.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: BML front-door agent task activity routes did not return native empty-activity proof"
    exit 1
  fi

  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "curl -fsS --max-time 10 -D /tmp/contributors.headers -o /tmp/contributors.body \
        'http://127.0.0.1:8080/api/contributors?limit=5&offset=0' \
        -H 'Accept: application/json' \
        && curl -fsS --max-time 10 -D /tmp/contributions.headers -o /tmp/contributions.body \
        'http://127.0.0.1:8080/api/contributions?limit=5&offset=0' \
        -H 'Accept: application/json' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/contributors.headers \
        && grep -qi '^X-Form-Handler: api_contributors' /tmp/contributors.headers \
        && grep -qi '^X-Form-Python-Authority: false' /tmp/contributors.headers \
        && grep -q '\"items\":\\[' /tmp/contributors.body \
        && grep -q '\"limit\":5' /tmp/contributors.body \
        && grep -q '\"offset\":0' /tmp/contributors.body \
        && grep -q '\"items\":\\[{' /tmp/contributors.body \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/contributions.headers \
        && grep -qi '^X-Form-Handler: api_contributions' /tmp/contributions.headers \
        && grep -qi '^X-Form-Python-Authority: false' /tmp/contributions.headers \
        && grep -q '\"items\":\\[' /tmp/contributions.body \
        && grep -q '\"limit\":5' /tmp/contributions.body \
        && grep -q '\"offset\":0' /tmp/contributions.body" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: BML front-door contribution read routes did not return native paginated proof"
    exit 1
  fi

  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "for spec in \
        'ideas-resonance|/api/ideas/resonance?limit=2|api_ideas_resonance' \
        'health|/api/health|api_health' \
        'ready|/api/ready|api_ready' \
        'gates-main-head|/api/gates/main-head|api_gates_main_head' \
        'agent-tasks|/api/agent/tasks?limit=1|api_agent_tasks' \
        'recent-concept-voices|/api/concepts/voices/recent?limit=2|api_concepts_voices_recent' \
        'recent-reactions|/api/reactions/recent?limit=2|api_reactions_recent' \
        'anonymous-meeting-traces|/api/meetings/anonymous-traces?limit=2|api_meetings_anonymous_traces' \
        'workspaces|/api/workspaces|api_workspaces' \
        'vitality|/api/workspaces/coherence-network/vitality|api_workspace_vitality' \
        'coherence-score|/api/coherence/score|api_coherence_score' \
        'graph-nodes|/api/graph/nodes?limit=1|api_graph_nodes' \
        'graph-node-detail|/api/graph/nodes/urs|api_graph_node_detail' \
        'idea-detail|/api/ideas/user-surfaces|api_idea_detail' \
        'graph-node-edges|/api/graph/nodes/asset:audible-B0D2DRHSDJ/edges?direction=both|api_graph_node_edges' \
        'presence-summary|/api/presence/summary|api_presence_summary' \
        'living-concept|/api/concepts/lc-circulation|api_concept_living_collective' \
        'edges|/api/edges?limit=2|api_edges' \
        'runtime-endpoints-summary|/api/runtime/endpoints/summary?limit=2|api_runtime_endpoints_summary' \
        'inventory-flow|/api/inventory/flow?idea_id=__native_inventory_canary__&list_item_limit=1&runtime_window_seconds=3600|api_inventory_flow' \
        'personal-feed|/api/feed/personal?limit=2|api_feed_personal' \
        'household-events|/api/household/events?limit=2|api_household_events' \
        'runtime-events|/api/runtime/events?limit=1&source=api|api_runtime_events' \
        'views-stats|/api/views/stats/lc-attuned-spaces?days=30|api_views_stats' \
        'reaction-summary|/api/reactions/concept/lc-attuned-spaces/summary|api_reaction_concept_summary' \
        'reaction-threads|/api/reactions/concept/lc-attuned-spaces/threads|api_reaction_concept_threads' \
        'concept-voices|/api/concepts/lc-attuned-spaces/voices|api_concept_voices' \
        'concept-carried-by|/api/concepts/lc-ceremony/carried-by|api_concept_carried_by' \
        'presence-resonances|/api/presences/asset:audible-B00DVN8U82/resonances|api_presence_resonances' \
        'presence-places|/api/presences/asset:audible-B0D2DRHSDJ/places|api_presence_places' \
        'spec-registry|/api/spec-registry?limit=2|api_spec_registry' \
        'spec-registry-detail|/api/spec-registry/web-ideas-specs-usage-pages|api_spec_registry_detail' \
        'idea-specs|/api/ideas/user-surfaces/specs|api_idea_specs' \
        'runtime-attention|/api/attention/kernel-runtime|api_attention_kernel_runtime' \
        'lenses|/api/lenses|api_lenses' \
        'sensings|/api/sensings?limit=2|api_sensings' \
        'translations-page-flow|/api/translations/page/flow|api_translations_entity'; do \
          name=\${spec%%|*}; rest=\${spec#*|}; url=\${rest%%|*}; handler=\${rest#*|}; \
          if ! curl -fsS --max-time 30 -D /tmp/promoted-\${name}.headers -o /tmp/promoted-\${name}.body \
            \"http://127.0.0.1:8080\${url}\" \
            -H 'Accept: application/json'; then \
              echo \"promoted route curl failed: \${name}\"; \
              exit 1; \
          fi; \
          if ! grep -qi '^X-Form-Router: native-kernel' /tmp/promoted-\${name}.headers; then \
            echo \"promoted route missing native router proof: \${name}\"; \
            sed -n '1,40p' /tmp/promoted-\${name}.headers; \
            head -c 500 /tmp/promoted-\${name}.body || true; \
            echo; \
            exit 1; \
          fi; \
          if ! grep -qi \"^X-Form-Handler: \${handler}\" /tmp/promoted-\${name}.headers; then \
            echo \"promoted route missing native handler proof: \${name}\"; \
            sed -n '1,40p' /tmp/promoted-\${name}.headers; \
            exit 1; \
          fi; \
          if ! grep -qi '^X-Form-Python-Authority: false' /tmp/promoted-\${name}.headers; then \
            echo \"promoted route missing native authority proof: \${name}\"; \
            sed -n '1,40p' /tmp/promoted-\${name}.headers; \
            exit 1; \
          fi; \
        done" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: BML front-door promoted read routes did not return native proof headers"
    exit 1
  fi

  deadline=$(( $(date +%s) + 120 ))
  probe_ok=0
  while (( $(date +%s) < deadline )); do
    if docker compose "${compose_args[@]}" exec -T kernel-router-bml-front-door sh -lc \
      "curl -fsS --max-time 10 -D /tmp/household-events.headers -o /tmp/household-events.body \
        'http://127.0.0.1:8080/api/household/events?limit=5' \
        -H 'Accept: application/json' \
        && grep -qi '^X-Form-Router: native-kernel' /tmp/household-events.headers \
        && grep -qi '^X-Form-Handler: api_household_events' /tmp/household-events.headers \
        && grep -qi '^X-Form-Python-Authority: false' /tmp/household-events.headers \
        && test \"\$(tr -d '[:space:]' </tmp/household-events.body)\" = '[]'" \
      2>&1 | tee -a "$LOG_FILE"; then
      probe_ok=1
      break
    fi
    sleep 3
  done
  if [[ "$probe_ok" != "1" ]]; then
    log "FAIL: BML front-door household events route did not return native empty-calendar proof"
    exit 1
  fi

  ended="$(date +%s)"
  elapsed=$((ended - started))
  log "kernel-router canary: running and locally receipt-proven (${elapsed}s)"
}

# Raise any service a prior cancelled rollout left stopped before the hard
# checks below — they verify the whole body, not only the rebuilt scope.
ensure_all_services_up || true

if wait_for_running api; then
  log "api container running"
else
  log "FAIL: api container did not reach running state within 180s"
  exit 1
fi

if wait_for_running web; then
  log "web container running"
else
  log "FAIL: web container did not reach running state within 180s"
  exit 1
fi

ensure_kernel_router_canary

sync_substrate_content
# Use DIFF_BASE (RUNNING_SHA when known) so substrate ingest catches any
# content the container is missing, not just what the repo's HEAD claims
# is new. Same reasoning as the rebuild gate above: the repo advances on
# git reset even when the container didn't see the change.
run_substrate_ingest "$DIFF_BASE" "$TARGET_SHA"

# Post-deploy assertion: the api container's /api/health must now report
# TARGET_SHA. If it doesn't, the deploy is silently stuck — either the
# build was a cache-noop with stale env, the restart didn't actually
# happen, or the env vars didn't propagate. Failing here makes the stall
# loud instead of letting workflow Verify-step retries chase a ghost.
# Every deploy path, including the build-free static path, performs the same
# independent local route observation and binds it to TARGET_SHA.
  # The api container reaching docker "running" state does not mean uvicorn is
  # already accepting requests on :8000. wait_for_running (and the --wait
  # fallback when no compose healthcheck fires) can return while the app is
  # still binding, so a single immediate curl returns an empty body, the sha
  # parses as "", and the deploy false-FAILs even though it is advancing. Poll
  # /api/health until it reports the target sha or the readiness budget is
  # spent. Still honest about a genuine non-advance: the build context is
  # rewritten to TARGET above, so GIT_COMMIT_SHA reflects the built code — a
  # real cache-noop keeps the old sha and still fails after the budget.
  POST_SHA=""
  POST_REACHED=0
  for ((verify_attempt = 1; verify_attempt <= 12; verify_attempt++)); do
    POST_HEALTH="$(docker compose -f "$COMPOSE_ROOT/docker-compose.yml" exec -T api \
        sh -lc 'curl -fsS --max-time 5 http://127.0.0.1:8000/api/health 2>/dev/null' \
        2>/dev/null || true)"
    if [[ -n "$POST_HEALTH" ]]; then
      POST_REACHED=1
      POST_SHA="$(printf '%s' "$POST_HEALTH" \
        | python3 -c 'import sys, json
try:
    print((json.loads(sys.stdin.read()).get("deployed_sha") or "").strip())
except Exception:
    pass' 2>/dev/null || true)"
      [[ "$POST_SHA" == "$TARGET_SHA" ]] && break
    fi
    log "Post-deploy verify: api not ready yet (attempt ${verify_attempt}/12); waiting 5s…"
    sleep 5
  done
  if [[ "$POST_SHA" != "$TARGET_SHA" ]]; then
    if [[ "$POST_REACHED" == "0" ]]; then
      log "FAIL: post-deploy /api/health never answered within the readiness budget (~60s)"
      log "      the api container did not become ready — check container startup logs"
    else
      log "FAIL: post-deploy /api/health reports deployed_sha=${POST_SHA:0:12} but target=${TARGET_SHA:0:12}"
      log "      the api container did not advance — build cache-noop, restart missed, or env didn't propagate"
    fi
    exit 1
  fi
  log "Post-deploy verify: api container at ${POST_SHA:0:12} ✓"

  bootstrap_and_verify_local_grounding || exit 1

log "Deploy complete (${TARGET_SHA:0:12}) — public health check runs next in CI"

# GitNexus sidecar (per specs/gitnexus-integration-experiment.md). Non-blocking:
# any failure is logged and the deploy still succeeds. The trial's spec
# explicitly counts install/staleness incidents as data, not setup bugs.
INSTALL_GITNEXUS="${COMPOSE_ROOT}/install-gitnexus.sh"
if [[ -x "$INSTALL_GITNEXUS" ]]; then
  REPO_DIR="$REPO_DIR" COMPOSE_ROOT="$COMPOSE_ROOT" LOG_FILE="$LOG_FILE" \
    "$INSTALL_GITNEXUS" || log "gitnexus: install script returned non-zero (deploy continues)"
else
  log "gitnexus: install script not present at $INSTALL_GITNEXUS (skipped)"
fi
