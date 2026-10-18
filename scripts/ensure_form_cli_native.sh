#!/usr/bin/env bash
# Select the image-built form-cli or build it once through the fkwu/Form gate.
# This shell is a retiring host carrier: Form owns the build and proof flow.
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KERNEL_ROOT="$ROOT/form"
PRINT_PATH=0

case "${1:-}" in
  "") ;;
  --print-path) PRINT_PATH=1 ;;
  --print-native-path) PRINT_PATH=2 ;;
  *)
    echo "usage: ensure_form_cli_native.sh [--print-path|--print-native-path]" >&2
    exit 2
    ;;
esac

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

host_os="$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]')"
host_arch="$(uname -m 2>/dev/null || printf unknown)"
case "$host_arch" in
  x86_64|amd64) host_arch=amd64 ;;
  aarch64|arm64) host_arch=arm64 ;;
esac
case "$host_os" in
  mingw*|msys*|cygwin*) host_os=windows ;;
esac

STDLIB_ROOT="$KERNEL_ROOT/form/form-stdlib"
[ -d "$STDLIB_ROOT" ] || STDLIB_ROOT="$KERNEL_ROOT/form-stdlib"
TARGET_DIR="$ROOT/.cache/form-cli-native/${host_os}-${host_arch}"
TARGET="$TARGET_DIR/form-cli"
RECEIPT="$ROOT/.cache/form-cli-native/selected.json"

if [ "$host_os" = windows ]; then
  TARGET="${TARGET}.exe"
fi

# Production images already contain the carrier built by the Form gate. Their
# immutable digest is the selection authority; startup does not rebuild or run
# a kernel validation loop.
if [ -r "$KERNEL_ROOT/form-cli.sha256" ]; then
  TARGET_DIR="$KERNEL_ROOT"
  TARGET="$KERNEL_ROOT/form-cli"
  RECEIPT="/root/.coherence-network/attestation/selected-form-cli-carrier.json"
fi
SOURCE_ID_FILE="${TARGET}.source.id"

write_receipt() {
  [ -r "$SOURCE_ID_FILE" ] || {
    echo "form-cli: source identity is missing: $SOURCE_ID_FILE" >&2
    return 1
  }
  native_target="$TARGET"
  if [ "$host_os" = windows ] && command -v cygpath >/dev/null 2>&1; then
    native_target="$(cygpath -m "$TARGET")"
  fi
  binary_digest="$(sha256_file "$TARGET")"
  source_digest="$(sha256_file "$SOURCE_ID_FILE")"
  expected_receipt="{\"schema\":\"selected-form-cli-carrier-v1\",\"native_path\":\"${native_target}\",\"binary_sha256\":\"${binary_digest}\",\"source_sha256\":\"${source_digest}\"}"
  mkdir -p "$(dirname "$RECEIPT")"
  receipt_tmp="${RECEIPT}.tmp.$$"
  printf '%s\n' "$expected_receipt" >"$receipt_tmp"
  mv -f "$receipt_tmp" "$RECEIPT"
}

finish() {
  write_receipt
  if [ "$PRINT_PATH" -eq 1 ]; then
    printf '%s\n' "$TARGET"
  elif [ "$PRINT_PATH" -eq 2 ] && [ "$host_os" = windows ] && command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$TARGET"
  elif [ "$PRINT_PATH" -eq 2 ]; then
    printf '%s\n' "$TARGET"
  fi
}

if [ -r "$KERNEL_ROOT/form-cli.sha256" ]; then
  [ -x "$TARGET" ] || {
    echo "form-cli: image-built carrier is missing" >&2
    exit 1
  }
  expected_binary="$(tr -d '\r\n' < "$KERNEL_ROOT/form-cli.sha256")"
  [ "$(sha256_file "$TARGET")" = "$expected_binary" ] || {
    echo "form-cli: image-built carrier digest mismatch" >&2
    exit 1
  }
  finish
  exit 0
fi

GATE="$KERNEL_ROOT/gate/form-cli-build-run.bml"
FKWU="$KERNEL_ROOT/fkwu"
[ -r "$GATE" ] || {
  echo "form-cli: Form build gate is missing: $GATE" >&2
  exit 1
}

mkdir -p "$TARGET_DIR"
if [ ! -x "$FKWU" ]; then
  cc -O2 -o "$FKWU" "$KERNEL_ROOT/runtime/fkwu-uni.c"
fi
CURRENT_SOURCE_ID="$(cd "$KERNEL_ROOT" && printf '{"source_id":1}\n' | ./fkwu gate/form-cli-build-run.bml)"
[ "${#CURRENT_SOURCE_ID}" -eq 16 ] || {
  echo "form-cli: Form source identity is unavailable" >&2
  exit 1
}

# A carrier is reusable only while its exact binary/source receipt still
# matches. A missing or changed receipt asks the Form gate to rebuild it.
if [ -x "$TARGET" ] && [ -r "$SOURCE_ID_FILE" ] && [ -r "$RECEIPT" ] \
  && [ "$(tr -d '\r\n' < "$SOURCE_ID_FILE")" = "$CURRENT_SOURCE_ID" ]; then
  binary_digest="$(sha256_file "$TARGET")"
  source_digest="$(sha256_file "$SOURCE_ID_FILE")"
  expected_receipt="{\"schema\":\"selected-form-cli-carrier-v1\",\"native_path\":\"${TARGET}\",\"binary_sha256\":\"${binary_digest}\",\"source_sha256\":\"${source_digest}\"}"
  if [ "$(tr -d '\r\n' < "$RECEIPT")" = "$expected_receipt" ]; then
    finish
    exit 0
  fi
fi

(cd "$KERNEL_ROOT" && printf '{"out":"%s","force_link":1,"cc":"cc"}\n' "$TARGET" | ./fkwu gate/form-cli-build-run.bml)
[ -x "$TARGET" ] || {
  echo "form-cli: Form build gate produced no executable" >&2
  exit 1
}
[ -r "$SOURCE_ID_FILE" ] && [ "$(tr -d '\r\n' < "$SOURCE_ID_FILE")" = "$CURRENT_SOURCE_ID" ] || {
  echo "form-cli: Form build gate produced no matching source identity" >&2
  exit 1
}
finish
