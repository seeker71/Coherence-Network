#!/usr/bin/env bash
# form_native_run.sh — run the PURE FORM agent runner (form-stdlib/form-native-run.fk)
# via the kernel. No C, no Python; host effects via the kernel's host-io builtins.
# Usage: form_native_run.sh "<task>" "<oracle-cmd>" [max-steps]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$ROOT/form/form-kernel-go" && go build -o bin-go .)
TASK="${1:?task}"; ORACLE="${2:-ollama run qwen2.5:72b}"; MAX="${3:-8}"
esc(){ printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
{ cat "$ROOT/form/form-stdlib/form-native-run.fk"
  echo "(print (fnr-run \"$(esc "$TASK")\" \"$(esc "$ORACLE")\" $MAX))"
} > "$work/run.fk"
"$GO" "$work/run.fk"
