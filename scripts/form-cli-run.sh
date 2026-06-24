#!/bin/sh
# form-cli-run.sh — minimal stdin carrier for form/form-cli (one line, then EOF).
# All fnri/receipt logic lives in Form; this script only pipes bytes.
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"
CLI="${FORM_CLI:-$ROOT/form/form-cli}"
[ -x "$CLI" ] || { echo "FAIL: $CLI missing — run: cd form && ./build-form-cli.sh" >&2; exit 1; }
printf '%s\n' "$*" | "$CLI"
