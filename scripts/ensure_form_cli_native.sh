#!/usr/bin/env bash
# ensure_form_cli_native.sh — the c-bootstrap fkwu form-cli, warmed once and cached.
#
# Warms the sovereign destination: standalone native form-cli (form/form-cli).
# Standard lane (2026-06-24): copies committed bootstrap/form-cli-<platform>
# when stamped — no bin-go, no clang. Maintainer regen:
# scripts/regen_standard_lane_binaries.sh
#
# Idempotent: present binary → instant no-op. Missing binary → bootstrap copy
# or one-time clang link from committed bootstrap C when platform binary absent.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM_DIR="$ROOT/form"
TARGET="$FORM_DIR/form-cli"
LOG="$FORM_DIR/form-stdlib/.cache/form-cli-native-build.log"

[ -x "$TARGET" ] && exit 0

mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
if (cd "$FORM_DIR" && FORM_STANDARD_LANE=1 ./build-form-cli.sh) >>"$LOG" 2>&1; then
  [ -x "$TARGET" ] && exit 0
fi

if ! command -v clang >/dev/null 2>&1; then
  for llvm_bin in "/c/Program Files/LLVM/bin" "/c/Program Files (x86)/LLVM/bin"; do
    if [[ -x "$llvm_bin/clang.exe" ]]; then
      export PATH="$llvm_bin:$PATH"
      break
    fi
  done
fi

if command -v clang >/dev/null 2>&1; then
  printf "⟐ c-bootstrap form-cli warming in background (bootstrap C + clang link); one-time, then cached. Guide: docs/coherence-substrate/form-cli-c-bootstrap.md\n"
  nohup bash -c "cd '$FORM_DIR' && ./build-form-cli.sh" >"$LOG" 2>&1 &
  disown 2>/dev/null || true
else
  printf "⟐ c-bootstrap form-cli not built; need bootstrap/form-cli-<platform> or clang. Guide: docs/coherence-substrate/form-cli-c-bootstrap.md\n"
fi
exit 0
