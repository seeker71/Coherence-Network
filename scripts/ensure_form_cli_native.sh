#!/usr/bin/env bash
# ensure_form_cli_native.sh — the c-bootstrap fkwu form-cli, warmed once and cached.
#
# Warms the sovereign destination: standalone native form-cli (form/form-cli).
# Standard lane (2026-06-24): copies committed bootstrap/form-cli-<platform>
# when stamped — no bin-go, no clang. Maintainer regen:
# form/scripts/regen_standard_lane_binaries.sh
#
# Idempotent: keeps a behaviorally verified host-native target, refreshes from
# the stamped committed platform binary when available, and otherwise performs
# one build-time clang link from the committed bootstrap C.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM_DIR="$ROOT/form"
PRINT_PATH=0
if [ "${1:-}" = "--print-path" ]; then
  PRINT_PATH=1
elif [ "${1:-}" = "--print-native-path" ]; then
  PRINT_PATH=2
elif [ "$#" -ne 0 ]; then
  echo "usage: ensure_form_cli_native.sh [--print-path|--print-native-path]" >&2
  exit 2
fi
host_os="$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')"
host_arch="$(uname -m 2>/dev/null || printf unknown)"
case "$host_arch" in
  x86_64|amd64) host_arch=amd64 ;;
  aarch64|arm64) host_arch=arm64 ;;
esac
case "$host_os" in
  mingw*|msys*|cygwin*) host_os=windows ;;
esac
if [ "${OS:-}" = "Windows_NT" ]; then host_os=windows; fi
TARGET_DIR="$ROOT/.cache/form-cli-native/${host_os}-${host_arch}"
TARGET="$TARGET_DIR/form-cli"
if [ "$host_os" = windows ]; then TARGET="${TARGET}.exe"; fi
# A production image carries an exact digest beside its image-built Linux
# carrier. That immutable image lane remains at /app/form/form-cli; development
# and CI carriers live outside the submodule so building for another host can
# never dirty or replace the pinned source checkout.
if [ -e "$FORM_DIR/form-cli.sha256" ]; then
  TARGET_DIR="$FORM_DIR"
  TARGET="$FORM_DIR/form-cli"
fi
LOG="$FORM_DIR/form-stdlib/.cache/form-cli-native-build.log"
RECEIPT="$ROOT/.cache/form-cli-native/selected.json"

mkdir -p "$(dirname "$LOG")" "$TARGET_DIR"

write_selected_receipt() {
  source_digest_file="$FORM_DIR/form-stdlib/bootstrap/form-cli.source.sha256"
  native_target="$TARGET"
  if [ "$host_os" = windows ] && command -v cygpath >/dev/null 2>&1; then
    native_target="$(cygpath -m "$TARGET")"
  fi
  binary_digest="$(sha256_file "$TARGET")"
  source_digest="$(tr -d '\r\n' < "$source_digest_file")"
  receipt_tmp="${RECEIPT}.tmp.$$"
  mkdir -p "$(dirname "$RECEIPT")"
  printf '{"schema":"selected-form-cli-carrier-v1","native_path":"%s","binary_sha256":"%s","source_sha256":"%s"}\n' \
    "$native_target" "$binary_digest" "$source_digest" >"$receipt_tmp"
  mv -f "$receipt_tmp" "$RECEIPT"
}

finish() {
  write_selected_receipt
  if [ "$PRINT_PATH" -eq 1 ]; then
    printf '%s\n' "$TARGET"
  elif [ "$PRINT_PATH" -eq 2 ]; then
    if [ "$host_os" = windows ]; then
      cygpath -w "$TARGET"
    else
      printf '%s\n' "$TARGET"
    fi
  fi
  exit 0
}

sha256_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    echo "form-cli: SHA-256 tool unavailable" >&2
    return 1
  fi
}

# Use the submodule's own carrier verifier at runtime as well as build time.
# Keeping one implementation prevents host-specific comparison drift between
# the authoritative builder and the consumer cache.
# shellcheck source=form/scripts/form_cli_bootstrap_proof.sh
source "$FORM_DIR/scripts/form_cli_bootstrap_proof.sh"

verify_carrier_identity() {
  source_digest_file="$FORM_DIR/form-stdlib/bootstrap/form-cli.source.sha256"
  [ -r "$source_digest_file" ] && [ -x "$TARGET" ] || return 1
  expected_source="$(cat "$source_digest_file")" || return 1
  [[ "$expected_source" =~ ^[0-9a-f]{64}$ ]] || return 1
  form_cli_verify_binary_identity "$TARGET" "$expected_source"
}

verify_image_built_lane() {
  manifest="$FORM_DIR/form-cli.sha256"
  [ -r "$manifest" ] || return 1
  IFS= read -r expected_binary <"$manifest" || return 1
  [[ "$expected_binary" =~ ^[0-9a-f]{64}$ ]] || return 1
  [ "$(sha256_file "$TARGET")" = "$expected_binary" ] || return 1
  verify_carrier_identity
}

# Production images carry a digest authority for the binary built from the
# exact checked-out source.  Never replace that carrier with a possibly stale
# committed platform bootstrap; prove and keep the image-built executable.
if [ -e "$FORM_DIR/form-cli.sha256" ]; then
  if verify_image_built_lane; then
    finish
  fi
  echo "form-cli: image-built native carrier failed digest/identity challenge" >&2
  exit 1
fi

# A host-native carrier built earlier in this checkout is reusable only after
# the same source-bound identity and challenge proof used by the image lane.
# This rejects the committed Darwin carrier when the checkout is on Windows.
if verify_carrier_identity; then
  finish
fi

refresh_from_standard_lane() {
  tmp="$(mktemp "$FORM_DIR/.form-cli-standard.XXXXXX")" || return 1
  if [[ "$TARGET" == *.exe ]]; then
    rm -f "$tmp"
    tmp="${tmp}.exe"
  fi
  if (cd "$FORM_DIR" && FORM_STANDARD_LANE=1 ./build-form-cli.sh "$tmp") >>"$LOG" 2>&1 && [ -x "$tmp" ]; then
    if [ ! -x "$TARGET" ] || ! cmp -s "$tmp" "$TARGET"; then
      mv -f "$tmp" "$TARGET"
      chmod +x "$TARGET"
    else
      rm -f "$tmp"
    fi
    return 0
  fi
  rm -f "$tmp"
  return 1
}

refresh_from_bootstrap_link() {
  tmp="$(mktemp "$FORM_DIR/.form-cli-linked.XXXXXX")" || return 1
  if [[ "$TARGET" == *.exe ]]; then
    rm -f "$tmp"
    tmp="${tmp}.exe"
  fi
  if (cd "$FORM_DIR" && ./build-form-cli.sh "$tmp") >>"$LOG" 2>&1 \
      && [ -x "$tmp" ]; then
    mv -f "$tmp" "$TARGET"
    chmod +x "$TARGET"
    verify_carrier_identity
    return
  fi
  rm -f "$tmp"
  return 1
}

if ! refresh_from_standard_lane && ! refresh_from_bootstrap_link; then
  echo "form-cli: committed bootstrap could not produce a native carrier" >&2
  tail -40 "$LOG" >&2 || true
  exit 1
fi
[[ -x "$TARGET" ]] || {
  echo "form-cli: standard-lane build produced no executable" >&2
  exit 1
}
verify_carrier_identity || {
  echo "form-cli: native carrier failed source-bound identity challenge" >&2
  exit 1
}
finish
