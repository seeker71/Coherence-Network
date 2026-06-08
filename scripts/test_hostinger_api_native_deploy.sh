#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

target_sha="70cbbec4314c7b8845596e661869b8d9ed478402"
old_sha="5dad3d6f0d7f48495b9644fde0e8d26572962ae1"

mkdir -p "$fixture_dir/bin"

cat >"$fixture_dir/project.json" <<JSON
{
  "content": "services:\\n  api:\\n    build:\\n      context: /docker/coherence-network/repo\\n      dockerfile: /docker/coherence-network/Dockerfile.api\\n  web:\\n    build:\\n      context: /docker/coherence-network/repo\\n      dockerfile: /docker/coherence-network/Dockerfile.web\\n      args:\\n        NEXT_PUBLIC_API_URL: \${NEXT_PUBLIC_API_URL}\\n  pulse:\\n    build:\\n      context: /docker/coherence-network/repo/pulse\\n      dockerfile: Dockerfile\\n  discord-bot:\\n    build:\\n      context: /docker/coherence-network\\n      dockerfile: /docker/coherence-network/Dockerfile.discord\\n",
  "environment": "POSTGRES_DB=coherence\\nPOSTGRES_PASSWORD=real-value-preserved\\nGIT_COMMIT_SHA=${old_sha}\\nDEPLOYED_SHA=${old_sha}\\n"
}
JSON

cat >"$fixture_dir/bin/gh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

case "$*" in
  "api repos/seeker71/Coherence-Network/branches/main --jq .commit.sha")
    printf '%s\n' "$TARGET_SHA"
    ;;
  *)
    echo "unexpected gh command: $*" >&2
    exit 9
    ;;
esac
SH
chmod +x "$fixture_dir/bin/gh"

cat >"$fixture_dir/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

out_file=""
data_file=""
method="GET"
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[$i]}" in
    -o)
      i=$((i + 1))
      out_file="${args[$i]}"
      ;;
    --data-binary)
      i=$((i + 1))
      data_file="${args[$i]#@}"
      ;;
    -X)
      i=$((i + 1))
      method="${args[$i]}"
      ;;
  esac
done

url=""
for arg in "${args[@]}"; do
  case "$arg" in
    http://*|https://*) url="$arg" ;;
  esac
done
case "$method $url" in
  "GET https://developers.hostinger.com/api/vps/v1/virtual-machines/1482815/docker/coherence-network")
    cat "$PROJECT_JSON"
    ;;
  "POST https://developers.hostinger.com/api/vps/v1/virtual-machines/1482815/docker")
    cp "$data_file" "$POSTED_JSON"
    if [[ -n "$out_file" ]]; then
      printf '{"id": "accepted"}\n' > "$out_file"
      printf '202'
    else
      printf '{"id": "accepted"}\n202'
    fi
    ;;
  *)
    echo "unexpected curl command: $method $url" >&2
    exit 9
    ;;
esac
SH
chmod +x "$fixture_dir/bin/curl"

posted_json="$fixture_dir/posted.json"

PATH="$fixture_dir/bin:$PATH" \
TARGET_SHA="$target_sha" \
PROJECT_JSON="$fixture_dir/project.json" \
POSTED_JSON="$posted_json" \
HOSTINGER_API_TOKEN="redacted-test-token" \
HOSTINGER_VIRTUAL_MACHINE_ID="1482815" \
HOSTINGER_API_NATIVE_WAIT=0 \
"$ROOT_DIR/scripts/hostinger_api_native_deploy.sh"

if ! jq -e --arg sha "$target_sha" '
  .project_name == "coherence-network"
  and (.content | contains("context: https://github.com/seeker71/Coherence-Network.git#" + $sha))
  and (.content | contains("context: https://github.com/seeker71/Coherence-Network.git#" + $sha + ":pulse"))
  and (.content | contains("dockerfile: Dockerfile.api"))
  and (.content | contains("dockerfile: Dockerfile.web"))
  and (.content | contains("dockerfile: discord-bot/Dockerfile"))
  and (.content | contains("DEPLOYED_SHA: ${DEPLOYED_SHA}"))
  and (.environment | contains("POSTGRES_PASSWORD=real-value-preserved"))
  and (.environment | contains("GIT_COMMIT_SHA=" + $sha))
  and (.environment | contains("DEPLOYED_SHA=" + $sha))
' "$posted_json" >/dev/null; then
  jq '{content, environment}' "$posted_json" >&2
  exit 1
fi

echo "PASS: hostinger_api_native_deploy preserves provider env and targets git SHA contexts"
