#!/usr/bin/env bash
# ensure_form_cli_kernel.sh — the native Form kernel that form-cli routes body-first
# questions on, built once on first startup and cached. Idempotent: a present binary
# is an instant no-op (the common path); a missing binary warms in the background from
# Go source when the toolchain is here (form-cli's own lazy build at bin/form-cli is the
# correctness net if a question arrives first); with no Go toolchain it degrades to a
# quiet note pointing at the installer. Carrier only — the body-first ROUTING is Form
# (form-cli-router/-sufficiency/-judge, four-way proven); this just keeps the engine warm.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="$ROOT/form/form-kernel-go"
GO_BIN="$GO_DIR/bin-go"

[ -x "$GO_BIN" ] && exit 0   # cached — instant, the common path

if command -v go >/dev/null 2>&1; then
  printf "⟐ form-cli native kernel warming in background (form/form-kernel-go) so body-first routing is ready; form-cli lazy-builds if asked sooner.\n"
  nohup bash -c "cd '$GO_DIR' && go build -o bin-go ." >/dev/null 2>&1 &
  disown 2>/dev/null || true
else
  printf "⟐ form-cli native kernel not built and no Go toolchain present; form-cli lazy-builds on first ask, or run install/form-cli-install.sh.\n"
fi
exit 0
