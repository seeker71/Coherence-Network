#!/usr/bin/env bash
# ensure_form_cli_native.sh — the c-bootstrap fkwu form-cli, warmed once and cached.
#
# Sibling of ensure_form_cli_kernel.sh. That one warms the Go ROUTING kernel
# (form/form-kernel-go/bin-go) so `form-cli ask` can ground body-first. THIS one
# warms the sovereign destination: the standalone native form-cli binary
# (form/form-cli) — the fkwu universal walker with the form-cli program baked in,
# emitted from Form recipes and compiled once to a self-contained executable that
# then runs with NO go/rust/clang/python/bash in its loop (ldd: libc + ld only).
#
# Idempotent: a present binary is an instant no-op (the common path). A missing
# binary warms in the BACKGROUND from Form source when the build toolchain is
# ready (clang compiles the emitted C ONCE). With no clang it degrades to a quiet
# note — the runtime is toolchain-free, but the one-time BUILD still needs clang.
#
# Strictly downstream of ensure_form_cli_kernel.sh: we only warm once the Go
# flattener (bin-go) is already present, so we never race that hook for the same
# `go build -o bin-go` output. On a fresh container the kernel warms this session
# and form-cli warms the next — a clean, race-free progression to the cached no-op.
#
# Carrier only. The body is Form (form-cli-repl.fk + form-cli.fk, four-way proven);
# this just makes the native CLI ready so an agent can reach for it body-first.
# Guide: docs/coherence-substrate/form-cli-c-bootstrap.md
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM_DIR="$ROOT/form"
TARGET="$FORM_DIR/form-cli"
GO_BIN="$FORM_DIR/form-kernel-go/bin-go"
LOG="$FORM_DIR/form-stdlib/.cache/form-cli-native-build.log"

[ -x "$TARGET" ] && exit 0   # cached — instant, the common path

if command -v clang >/dev/null 2>&1 && [ -x "$GO_BIN" ]; then
  printf "⟐ c-bootstrap form-cli warming in background (form/build-form-cli.sh -> form/form-cli); one-time ~1min, then cached and toolchain-free. Guide: docs/coherence-substrate/form-cli-c-bootstrap.md\n"
  mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
  nohup bash -c "cd '$FORM_DIR' && ./build-form-cli.sh" >"$LOG" 2>&1 &
  disown 2>/dev/null || true
elif ! command -v clang >/dev/null 2>&1; then
  printf "⟐ c-bootstrap form-cli not built and clang (the one-time build compiler) is absent; build later with: (cd form && ./build-form-cli.sh). Guide: docs/coherence-substrate/form-cli-c-bootstrap.md\n"
else
  printf "⟐ c-bootstrap form-cli waits on the Go flattener (bin-go) warming this session; it builds next session, or now with: (cd form && ./build-form-cli.sh). Guide: docs/coherence-substrate/form-cli-c-bootstrap.md\n"
fi
exit 0
