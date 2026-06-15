#!/usr/bin/env bash
# form_cli_run.sh — the form-cli RUNNER as a native binary, emitted by a Form recipe
# (form-stdlib/form-cli-run.fk: fcrun-emit), compiled with cc, run native. No Python.
# Walks the Hermes tool protocol (form-agent-protocol.fk). Oracle = a host command
# reading the prompt on stdin: `ollama run qwen2.5:72b` (local, cross-train teacher),
# `ollama run llama3.2:3b` (fast local), or `claude -p` (the strong subscription CLI).
# Every turn is captured to ~/.coherence-network/form-cli-runs.log (the corpus).
#
# Usage:
#   scripts/form_cli_run.sh --build-only
#   scripts/form_cli_run.sh "<task>" "<oracle-cmd>" [max-steps]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fcrun.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ printf '(do\n'
  cat "$FORM/form-stdlib/form-cli-run.fk"
  printf '\n(print "==C==")\n(print (fcrun-emit))\n(print "==END==")\n0)\n'
} > "$work/emit.fk"
"$GO" "$work/emit.fk" 2>/dev/null | awk '/^==C==$/{f=1;next} /^==END==$/{f=0} f' > "$work/run.c"
[[ -s "$work/run.c" ]] || { echo "FAIL: Form emitted no C"; exit 1; }
echo "Form-emitted runner: $(wc -l < "$work/run.c" | tr -d ' ') lines of C — compiled by cc, run native (no Python)"
cc -O2 -o "$work/form-cli-run" "$work/run.c" 2>"$work/cc.err" || {
  echo "FAIL: cc could not compile the emitted C"; sed 's/^/  /' "$work/cc.err"; exit 1; }
echo "compiled: $work/form-cli-run"

if [[ "${1:-}" == "--build-only" || -z "${1:-}" ]]; then
  echo "build-only OK — give a task + oracle to run it"; exit 0
fi
TASK="$1"; ORACLE="${2:-ollama run qwen2.5:72b}"; STEPS="${3:-10}"
echo "running: form-cli-run \"$TASK\"  oracle=[$ORACLE]  max-steps=$STEPS"
"$work/form-cli-run" "$TASK" "$ORACLE" "$STEPS"
