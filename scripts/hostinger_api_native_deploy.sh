#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-seeker71/Coherence-Network}"
PROJECT_NAME="${HOSTINGER_PROJECT_NAME:-coherence-network}"
VM_ID="${1:-${HOSTINGER_VIRTUAL_MACHINE_ID:-}}"
TARGET_SHA="${2:-${TARGET_SHA:-}}"
HOSTINGER_API_BASE="${HOSTINGER_API_BASE:-https://developers.hostinger.com}"
PUBLIC_API_BASE_URL="${PUBLIC_API_BASE_URL:-https://api.coherencycoin.com}"
WAIT_FOR_PUBLIC="${HOSTINGER_API_NATIVE_WAIT:-1}"
TIMEOUT_SECONDS="${HOSTINGER_API_NATIVE_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${HOSTINGER_API_NATIVE_POLL_SECONDS:-20}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 2
  fi
}

need curl
need jq
need perl
need gh
need docker

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required" >&2
  exit 2
fi

if [[ -z "${HOSTINGER_API_TOKEN:-}" ]]; then
  echo "HOSTINGER_API_TOKEN is required" >&2
  exit 2
fi

if [[ -z "$VM_ID" ]]; then
  echo "Hostinger virtual machine id is required" >&2
  exit 2
fi

if [[ -z "$TARGET_SHA" ]]; then
  TARGET_SHA="$(gh api "repos/${REPO}/branches/main" --jq '.commit.sha')"
fi

if [[ ! "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "target SHA must be a full 40-character git SHA: $TARGET_SHA" >&2
  exit 2
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

project_json="$tmp_dir/project.json"
compose_in="$tmp_dir/docker-compose.yml"
compose_rebased="$tmp_dir/docker-compose.rebased.yml"
compose_overlay="$tmp_dir/docker-compose.kernel-front-door.yml"
compose_out="$tmp_dir/docker-compose.api-native.yml"
env_in="$tmp_dir/project.env"
env_out="$tmp_dir/project.updated.env"
request_json="$tmp_dir/request.json"
response_json="$tmp_dir/response.json"

project_url="${HOSTINGER_API_BASE%/}/api/vps/v1/virtual-machines/${VM_ID}/docker/${PROJECT_NAME}"
deploy_url="${HOSTINGER_API_BASE%/}/api/vps/v1/virtual-machines/${VM_ID}/docker"

curl -fsS \
  -H "Authorization: Bearer ${HOSTINGER_API_TOKEN}" \
  -H "Accept: application/json" \
  "$project_url" \
  > "$project_json"

jq -er '.content' "$project_json" > "$compose_in"
jq -r '.environment // ""' "$project_json" > "$env_in"

git_context="https://github.com/${REPO}.git#${TARGET_SHA}"
pulse_context="${git_context}:pulse"

GIT_CONTEXT="$git_context" PULSE_CONTEXT="$pulse_context" perl -0pe '
  s{context:\s*/docker/coherence-network/repo/pulse}{context: $ENV{PULSE_CONTEXT}}g;
  s{context:\s*/docker/coherence-network/repo}{context: $ENV{GIT_CONTEXT}}g;
  s{context:\s*/docker/coherence-network(?=\s)}{context: $ENV{GIT_CONTEXT}}g;
  s{dockerfile:\s*/docker/coherence-network/Dockerfile\.api}{dockerfile: Dockerfile.api}g;
  s{dockerfile:\s*/docker/coherence-network/Dockerfile\.web}{dockerfile: Dockerfile.web}g;
  s{dockerfile:\s*/docker/coherence-network/Dockerfile\.discord}{dockerfile: discord-bot/Dockerfile}g;
  if ($_ !~ /DEPLOYED_SHA:\s*\$\{DEPLOYED_SHA\}/) {
    s{(NEXT_PUBLIC_API_URL:\s*\$\{NEXT_PUBLIC_API_URL\}\n)}{$1        DEPLOYED_SHA: \${DEPLOYED_SHA}\n};
  }
' "$compose_in" > "$compose_rebased"

cat > "$compose_overlay" <<YAML
services:
  api:
    labels:
      traefik.enable: "false"

  kernel-router:
    build:
      context: ${git_context}
      dockerfile: Dockerfile.kernel-router
    image: coherence-network-kernel-router:\${DEPLOYED_SHA}
    restart: unless-stopped
    environment:
      UPSTREAM_URL: http://api:8000
      KERNEL_ROUTER_PORT: "8080"
      ROUTES_FILE: /routes/production-routes.fk
      STDLIB_DIR: /app/form/form-stdlib
    depends_on:
      - api
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.coherence-api.rule=Host(\`api.coherencycoin.com\`)"
      - "traefik.http.routers.coherence-api.entrypoints=websecure"
      - "traefik.http.routers.coherence-api.tls.certresolver=letsencrypt"
      - "traefik.http.services.coherence-api.loadbalancer.server.port=8080"
YAML

docker compose \
  --project-name "$PROJECT_NAME" \
  -f "$compose_rebased" \
  -f "$compose_overlay" \
  config --no-interpolate \
  > "$compose_out"

if ! grep -q 'kernel-router:' "$compose_out"; then
  echo "hostinger-api-native: kernel-router service missing after compose merge" >&2
  exit 1
fi
if ! grep -q 'ROUTES_FILE: /routes/production-routes.fk' "$compose_out"; then
  echo "hostinger-api-native: production routes manifest missing after compose merge" >&2
  exit 1
fi
if ! grep -q 'traefik.enable=false' "$compose_out"; then
  echo "hostinger-api-native: api service was not removed from public Traefik routing" >&2
  exit 1
fi
if ! grep -q 'traefik.http.services.coherence-api.loadbalancer.server.port=8080' "$compose_out"; then
  echo "hostinger-api-native: kernel-router Traefik service port missing after compose merge" >&2
  exit 1
fi

awk -v sha="$TARGET_SHA" '
  BEGIN {
    desired["GIT_COMMIT_SHA"] = sha
    desired["DEPLOYED_SHA"] = sha
  }
  /^[[:space:]]*#/ || $0 !~ /=/ {
    print
    next
  }
  {
    split($0, parts, "=")
    key = parts[1]
    if (key in desired) {
      print key "=" desired[key]
      seen[key] = 1
    } else {
      print
    }
  }
  END {
    for (key in desired) {
      if (!(key in seen)) {
        print key "=" desired[key]
      }
    }
  }
' "$env_in" > "$env_out"

jq -n \
  --arg project_name "$PROJECT_NAME" \
  --rawfile content "$compose_out" \
  --rawfile environment "$env_out" \
  '{project_name: $project_name, content: $content, environment: $environment}' \
  > "$request_json"

echo "hostinger-api-native: deploying project=${PROJECT_NAME} vm=${VM_ID} target=${TARGET_SHA} front-door=kernel-router"

http_status="$(
  curl -sS -w '%{http_code}' \
    -X POST \
    -H "Authorization: Bearer ${HOSTINGER_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary "@${request_json}" \
    "$deploy_url" \
    -o "$response_json"
)"

if [[ "$http_status" -lt 200 || "$http_status" -ge 300 ]]; then
  echo "hostinger-api-native: deploy request failed status=${http_status}" >&2
  jq -r '.message // .error // .' "$response_json" >&2 || sed -n '1,80p' "$response_json" >&2
  exit 1
fi

echo "hostinger-api-native: deploy accepted status=${http_status}"

if [[ "$WAIT_FOR_PUBLIC" != "1" ]]; then
  exit 0
fi

deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
while :; do
  live_sha="$(
    curl -fsS "${PUBLIC_API_BASE_URL%/}/api/health" \
      | jq -r '.deployed_sha // ""' \
      || true
  )"
  if [[ "$live_sha" == "$TARGET_SHA" ]]; then
    echo "hostinger-api-native: public API aligned target=${TARGET_SHA}"
    exit 0
  fi
  if (( $(date +%s) >= deadline )); then
    echo "hostinger-api-native: timeout waiting for public API SHA parity live=${live_sha:-unknown} target=${TARGET_SHA}" >&2
    exit 1
  fi
  echo "hostinger-api-native: waiting live=${live_sha:-unknown} target=${TARGET_SHA}"
  sleep "$POLL_SECONDS"
done
