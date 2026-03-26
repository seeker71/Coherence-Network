#!/usr/bin/env bash
# Publish cli/ and mcp-server/ to npm when local semver is strictly greater than registry.
# NPM_TOKEN must be set for actual publish. Idempotent when versions match.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export NPM_CONFIG_FUND=false
export NPM_CONFIG_AUDIT=false

if [[ -n "${NPM_TOKEN:-}" ]]; then
  echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > "${ROOT}/.npmrc"
  trap 'rm -f "${ROOT}/.npmrc"' EXIT
fi

is_newer() {
  # true if $1 sorts after $2 with sort -V (strictly greater semver-ish)
  local a="$1" b="$2"
  [[ "$a" != "$b" && "$(printf '%s\n%s\n' "$b" "$a" | sort -V | tail -n1)" == "$a" ]]
}

publish_pkg() {
  local dir="$1"
  local pkg_json="${ROOT}/${dir}/package.json"
  [[ -f "$pkg_json" ]] || return 0
  local name ver
  name="$(jq -r .name "$pkg_json")"
  ver="$(jq -r .version "$pkg_json")"
  local reg
  reg="$(npm view "$name" version 2>/dev/null || true)"
  if [[ -z "${NPM_TOKEN:-}" ]]; then
    echo "npm: skip publish (no NPM_TOKEN) — $name local=$ver registry=${reg:-<none>}"
    return 0
  fi
  if [[ -z "$reg" ]]; then
    echo "npm: registry has no $name; publishing $name@$ver"
    (cd "${ROOT}/${dir}" && npm publish --access public)
    return 0
  fi
  if [[ "$ver" == "$reg" ]]; then
    echo "npm: skip $name (already published $ver)"
    return 0
  fi
  if is_newer "$ver" "$reg"; then
    echo "npm: publishing $name@$ver (registry was $reg)"
    (cd "${ROOT}/${dir}" && npm publish --access public)
    return 0
  fi
  echo "npm: skip $name local $ver not greater than registry $reg"
  return 0
}

for d in cli mcp-server; do
  publish_pkg "$d"
done
