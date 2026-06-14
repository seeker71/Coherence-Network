#!/usr/bin/env bash
# form_agent.sh — the form-cli agent loop as a NATIVE binary, emitted by a Form
# recipe (form-stdlib/form-cli-agent.fk: fa-emit), compiled with cc, run native.
# No Python anywhere. The oracle is a host command that reads the prompt on stdin:
#   `ollama run <model>`   (local, no key, sovereign)
#   `claude -p`            (the strong CLI you are using)
# There is no paid API endpoint. The loop uses a line protocol (BASH/READ/WRITE/
# DONE) so the body needs no JSON host bridge.
#
# Usage:
#   scripts/form_agent.sh --build-only
#   scripts/form_agent.sh "<task>" "<oracle-cmd>" [max-steps]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fagent.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# Form emits the C source for the loop (fa-emit). The recipe is the body.
{ printf '(do\n'
  cat "$FORM/form-stdlib/form-cli-agent.fk"
  printf '\n(print "==C==")\n(print (fa-emit))\n(print "==END==")\n0)\n'
} > "$work/emit.fk"
"$GO" "$work/emit.fk" 2>/dev/null | awk '/^==C==$/{f=1;next} /^==END==$/{f=0} f' > "$work/agent.c"
[[ -s "$work/agent.c" ]] || { echo "FAIL: Form emitted no C (kernel could not run fa-emit)"; exit 1; }
echo "Form-emitted agent loop: $(wc -l < "$work/agent.c" | tr -d ' ') lines of C — compiled by cc, run native (no Python)"
cc -O2 -o "$work/form-agent" "$work/agent.c" 2>"$work/cc.err" || {
  echo "FAIL: cc could not compile the emitted C"; sed 's/^/  /' "$work/cc.err"; exit 1; }
echo "compiled: $work/form-agent"

if [[ "${1:-}" == "--build-only" || -z "${1:-}" ]]; then
  echo "build-only OK — give a task + oracle to run it"; exit 0
fi
TASK="$1"; ORACLE="${2:-ollama run llama3.2:3b}"; STEPS="${3:-8}"
echo "running: form-agent \"$TASK\"  oracle=[$ORACLE]  max-steps=$STEPS"
"$work/form-agent" "$TASK" "$ORACLE" "$STEPS"
