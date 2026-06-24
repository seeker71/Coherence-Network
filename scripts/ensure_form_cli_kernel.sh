#!/usr/bin/env bash
# ensure_form_cli_kernel.sh — warm the Go bootstrap flattener (bin-go) that
# form-cli routing and build-form-cli.sh depend on. Idempotent. Sibling:
# ensure_form_cli_native.sh warms the c-bootstrapped fkwu form-cli (the agent
# runtime target). bin-go is bootstrap compost, not the runtime — see CLAUDE.md.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="$ROOT/form/form-kernel-go"
GO_BIN="$GO_DIR/bin-go"

[ -x "$GO_BIN" ] && exit 0

if command -v go >/dev/null 2>&1; then
  printf "⟐ form-cli bootstrap flattener warming in background (form/form-kernel-go/bin-go); c-bootstrap form-cli follows via ensure_form_cli_native.sh.\n"
  nohup bash -c "cd '$GO_DIR' && go build -o bin-go ." >/dev/null 2>&1 &
  disown 2>/dev/null || true
else
  printf "⟐ bootstrap flattener not built and no Go toolchain; run install/form-cli-install.sh or use a release binary.\n"
fi
exit 0
