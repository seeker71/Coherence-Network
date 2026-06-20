#!/usr/bin/env bash
# form_cli_ask.sh — thin WITNESS: the kernel runs form-cli-ask.fk (the body is Form, not this shell).
#
# This carrier only marshals args and invokes the Go kernel on the recipe — exactly the
# form_native_run.sh pattern. The ask flow (local oracle -> judge -> sufficiency verdict ->
# escalate to claude -p) lives in form-stdlib/form-cli-ask.fk and executes IN the kernel via host-io.
#
# Usage: form_cli_ask.sh [-m local-model] [-j judge] [--remote "claude -p"] [--trust N] "question..."
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
[[ -x "$GO" ]] || (cd "$ROOT/form/form-kernel-go" && go build -o bin-go .)

MODEL="coder"; JUDGE="llama3.2:3b"; REMOTE="claude -p"; TRUST=60; RETRIES=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--model)  MODEL="$2"; shift 2 ;;
    -j|--judge)  JUDGE="$2"; shift 2 ;;
    --remote)    REMOTE="$2"; shift 2 ;;
    --trust)     TRUST="$2"; shift 2 ;;
    --retries)   RETRIES="$2"; shift 2 ;;
    *)           break ;;
  esac
done
Q="$*"
[[ -n "$Q" ]] || { echo "usage: form-cli ask+ [-m model] [-j judge] \"question\"" >&2; exit 2; }

esc(){ printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
{ cat "$STD/form-cli-router.fk" "$STD/form-cli-judge.fk" "$STD/form-cli-sufficiency.fk" "$STD/form-cli-ask.fk"
  echo "(print (fca-ask \"$(esc "$Q")\" \"$(esc "$MODEL")\" \"$(esc "$JUDGE")\" \"$(esc "$REMOTE")\" $TRUST $RETRIES))"
} > "$work/ask.fk"
"$GO" "$work/ask.fk" 2>/dev/null | sed '/^null$/d'
