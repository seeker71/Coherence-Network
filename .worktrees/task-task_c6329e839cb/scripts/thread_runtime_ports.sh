#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STATE_DIR="${HOME}/.coherence-thread-runtime"

thread_runtime_state_dir() {
  mkdir -p "${STATE_DIR}"
  printf '%s\n' "${STATE_DIR}"
}

thread_runtime_thread_key() {
  local repo_root
  local branch
  local raw
  local digest

  repo_root="$(git -C "${ROOT_DIR}" rev-parse --show-toplevel 2>/dev/null || pwd -P)"
  branch="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "detached")"
  raw="${repo_root}::${branch}::${USER}"

  if command -v sha256sum >/dev/null 2>&1; then
    digest="$(printf '%s' "${raw}" | sha256sum | awk '{print $1}')"
  else
    digest="$(printf '%s' "${raw}" | shasum -a 256 | awk '{print $1}')"
  fi

  printf '%s-%s\n' "$(echo "${repo_root##*/}")" "${digest:0:16}"
}

thread_runtime_is_port_used() {
  local port="$1"
  lsof -iTCP:"${port}" -sTCP:LISTEN -t >/dev/null 2>&1
}

thread_runtime_record_usage() {
  local state_dir
  local allocation_file
  local allocation_dir
  local updated_at

  state_dir="$(thread_runtime_state_dir)"
  allocation_dir="${state_dir}/allocations"
  mkdir -p "${allocation_dir}"
  updated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  allocation_file="${allocation_dir}/${THREAD_RUNTIME_KEY}.env"
  cat > "${allocation_file}" <<EOF
THREAD_RUNTIME_API_HOST="${THREAD_RUNTIME_API_HOST}"
THREAD_RUNTIME_WEB_HOST="${THREAD_RUNTIME_WEB_HOST}"
THREAD_RUNTIME_API_PORT="${THREAD_RUNTIME_API_PORT}"
THREAD_RUNTIME_WEB_PORT="${THREAD_RUNTIME_WEB_PORT}"
THREAD_RUNTIME_API_BASE="http://${THREAD_RUNTIME_API_HOST}:${THREAD_RUNTIME_API_PORT}"
THREAD_RUNTIME_WEB_BASE="http://${THREAD_RUNTIME_WEB_HOST}:${THREAD_RUNTIME_WEB_PORT}"
THREAD_RUNTIME_UPDATED_AT="${updated_at}"
EOF

  printf '%s\tapi=%s\tweb=%s\thost=%s\n' \
    "${updated_at}" \
    "${THREAD_RUNTIME_API_PORT}" \
    "${THREAD_RUNTIME_WEB_PORT}" \
    "${THREAD_RUNTIME_API_HOST}" >> "${state_dir}/usage.log"
}

thread_runtime_dump_usage() {
  local state_dir="${STATE_DIR}"
  local allocation_dir="${state_dir}/allocations"
  local file
  local key
  local api_port
  local web_port
  local host
  local updated

  echo "thread runtime port usage:"
  if [[ ! -d "${allocation_dir}" ]]; then
    echo "(no allocations recorded)"
    return 0
  fi

  for file in "${allocation_dir}"/*.env; do
    [[ -f "${file}" ]] || continue
    # shellcheck disable=SC1090
    source "${file}"
    key="$(basename "${file%.env}")"
    updated="${THREAD_RUNTIME_UPDATED_AT:-unknown}"
    host="${THREAD_RUNTIME_API_HOST:-127.0.0.1}"
    api_port="${THREAD_RUNTIME_API_PORT:-unknown}"
    web_port="${THREAD_RUNTIME_WEB_PORT:-unknown}"
    printf "  %s -> api=%s web=%s host=%s updated=%s\n" \
      "${key}" \
      "${api_port}" \
      "${web_port}" \
      "${host}" \
      "${updated}"
  done
}

thread_runtime_resolve_ports() {
  local base_api_port="$1"
  local base_web_port="$2"
  local api_host="${3:-127.0.0.1}"
  local web_host="${4:-${api_host}}"
  local state_dir
  local allocation_dir
  local cached_file
  local attempt=0
  local max_offset=400
  local seed
  local offset
  local api_port
  local web_port
  local selected_api=""
  local selected_web=""
  local key

  if [[ -n "${THREAD_RUNTIME_KEY:-}" ]]; then
    key="${THREAD_RUNTIME_KEY}"
  else
    key="$(thread_runtime_thread_key)"
    export THREAD_RUNTIME_KEY="${key}"
  fi

  state_dir="$(thread_runtime_state_dir)"
  allocation_dir="${state_dir}/allocations"
  mkdir -p "${allocation_dir}"
  cached_file="${allocation_dir}/${key}.env"

  THREAD_RUNTIME_API_HOST="${api_host}"
  THREAD_RUNTIME_WEB_HOST="${web_host}"
  export THREAD_RUNTIME_API_HOST THREAD_RUNTIME_WEB_HOST
  export THREAD_RUNTIME_KEY

  if [[ -f "${cached_file}" ]]; then
    # shellcheck disable=SC1090
    source "${cached_file}"
    if [[ -n "${THREAD_RUNTIME_API_PORT:-}" && -n "${THREAD_RUNTIME_WEB_PORT:-}" ]]; then
      if ! thread_runtime_is_port_used "${THREAD_RUNTIME_API_PORT}" && ! thread_runtime_is_port_used "${THREAD_RUNTIME_WEB_PORT}"; then
        export THREAD_RUNTIME_API_BASE="http://${THREAD_RUNTIME_API_HOST}:${THREAD_RUNTIME_API_PORT}"
        export THREAD_RUNTIME_WEB_BASE="http://${THREAD_RUNTIME_WEB_HOST}:${THREAD_RUNTIME_WEB_PORT}"
        thread_runtime_record_usage
        return 0
      fi
    fi
  fi

  if command -v sha256sum >/dev/null 2>&1; then
    seed="$(printf '%s' "${key}" | sha256sum | awk '{print $1}')"
  else
    seed="$(printf '%s' "${key}" | shasum -a 256 | awk '{print $1}')"
  fi
  offset=$((0x${seed:0:6} % 200))

  while ((attempt <= max_offset)); do
    api_port=$((base_api_port + offset + attempt))
    web_port=$((base_web_port + offset + attempt))

    if ! thread_runtime_is_port_used "${api_port}" && ! thread_runtime_is_port_used "${web_port}"; then
      selected_api="${api_port}"
      selected_web="${web_port}"
      break
    fi
    ((attempt += 1))
  done

  if [[ -z "${selected_api}" || -z "${selected_web}" ]]; then
    echo "thread runtime: unable to allocate free API/web ports near ${base_api_port}/${base_web_port}" >&2
    return 1
  fi

  export THREAD_RUNTIME_API_PORT="${selected_api}"
  export THREAD_RUNTIME_WEB_PORT="${selected_web}"
  export THREAD_RUNTIME_API_BASE="http://${THREAD_RUNTIME_API_HOST}:${THREAD_RUNTIME_API_PORT}"
  export THREAD_RUNTIME_WEB_BASE="http://${THREAD_RUNTIME_WEB_HOST}:${THREAD_RUNTIME_WEB_PORT}"
  thread_runtime_record_usage
}
