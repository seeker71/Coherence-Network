#!/usr/bin/env bash
# form_cli_ask.sh — thin WITNESS for `form-cli ask+`. The body is Form: the kernel
# runs form-cli-ask-plus.fk (local-first; the four-way-proven sufficiency gate
# escalates to the subscription oracle when local is not enough — claude-code quality).
#
# This carrier only source-compiles the BML sections the body is written in — core,
# http-client, form-cli-ask (the local lane), form-cli-ask-plus (the escalating flow)
# — exactly the way validate.sh does (form-source-compile-file through the compiler
# chain, content-cached), links them with the s-expr gate recipes (router / judge /
# sufficiency / ask-gate), and invokes the kernel on the recipe. The decision math is
# the gate's, proven four-way; this shell marshals args and wires the carriers.
#
# Usage: form_cli_ask.sh [-m local-model] [-j judge] [--remote "claude -p"] [--trust N] [--retries N] [--judge-gate] "question..."
#   By default the local body is trusted (sovereignty-first): a usable local answer
#   stands, and only a local FAILURE (empty / error / refusal) escalates to the oracle.
#   --judge-gate turns on the judge model as the content scorer — claude-code quality at
#   the cost of the judge's latency and noise (a small judge can mis-score a good answer).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
[[ -x "$GO" ]] || (cd "$ROOT/form/form-kernel-go" && go build -o bin-go .)

MODEL="coder"; JUDGE="llama3.2:3b"; REMOTE="claude -p"; TRUST=60; RETRIES=1; JUDGE_GATE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--model)  MODEL="$2"; shift 2 ;;
    -j|--judge)  JUDGE="$2"; shift 2 ;;
    --remote)    REMOTE="$2"; shift 2 ;;
    --trust)     TRUST="$2"; shift 2 ;;
    --retries)   RETRIES="$2"; shift 2 ;;
    --judge-gate) JUDGE_GATE=1; shift ;;
    *)           break ;;
  esac
done
Q="$*"
[[ -n "$Q" ]] || { echo "usage: form-cli ask+ [-m model] [-j judge] [--remote CMD] \"question\"" >&2; exit 2; }

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

# ── source-compile the BML sections (content-cached, shared with validate.sh) ──
# A `section [...]` file is the BML maintenance dialect; the kernel runs the lowered
# s-expr the source-compiler emits. The cache key is the file content + the compiler
# chain + the kernel, so an unchanged source compiles once across runs (and shares
# validate.sh's cache dir), and a real compile failure surfaces instead of being fed
# raw to the kernel as a parse error.
CACHE="$STD/.cache/source-compiled"; mkdir -p "$CACHE"
CHAIN=("$STD/form-ontology-loader.fk" "$STD/line-grammar.fk" "$STD/bmf-core.fk" "$STD/bmf-grammar.fk" "$STD/bml.fk" "$STD/bml-source.fk" "$STD/source-compiler.fk" "$STD/grammars/form-bml.fk" "$STD/form-bml-lower.fk")
hash16() { cat "$@" 2>/dev/null | shasum -a 256 | cut -c1-16; }
stamp="$(hash16 "${CHAIN[@]}" "$GO")"
compile_bml() {  # src -> path to compiled s-expr on stdout (cached); exits on failure
  local src="$1" key cached out drv
  key="$(hash16 "$src")-$stamp"; cached="$CACHE/$key.fk"
  if [[ ! -s "$cached" ]]; then
    out="$(mktemp "$CACHE/.tmp.XXXXXX")"; drv="$work/compile.fk"
    printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$out" > "$drv"
    if "$GO" "${CHAIN[@]}" "$drv" >/dev/null 2>"$work/cerr" && [[ -s "$out" ]]; then
      mv -f "$out" "$cached"
    else
      echo "form-cli ask+: failed to source-compile $src" >&2
      sed 's/^/  /' "$work/cerr" >&2
      rm -f "$out"; exit 3
    fi
  fi
  printf '%s\n' "$cached"
}
CORE="$(compile_bml "$STD/core.fk")"
HTTP="$(compile_bml "$STD/http-client.fk")"
ASK="$(compile_bml "$STD/form-cli-ask.fk")"
ASKPLUS="$(compile_bml "$STD/form-cli-ask-plus.fk")"

# ── invoke: local-first ask through the escalating flow, traced ──
# fca-ask-plus-traced returns the live trust row on line 1 and the answer below it.
# The row (the per-query "field": native vs rented, grounded/freq/sufficient) goes to
# stderr — visible at a terminal, out of the way of a piped answer; the answer goes to
# stdout. The trust LOGIC is Form (form-cli-ask-gate.fk, four-way proven); the shell
# only routes the two streams.
esc(){ printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
printf '(print (fca-ask-plus-traced "%s" "%s" "%s" "%s" %s %s %s))\n' \
  "$(esc "$Q")" "$(esc "$MODEL")" "$(esc "$JUDGE")" "$(esc "$REMOTE")" "$TRUST" "$RETRIES" "$JUDGE_GATE" > "$work/ask.fk"

out="$("$GO" "$CORE" "$HTTP" "$ASK" \
  "$STD/form-cli-router.fk" "$STD/form-cli-judge.fk" "$STD/form-cli-sufficiency.fk" "$STD/trust-row.fk" "$STD/form-cli-ask-gate.fk" \
  "$ASKPLUS" "$work/ask.fk" | sed '/^null$/d')"
printf '%s\n' "$out" | sed -n '1p' >&2   # line 1: the live trust row -> stderr
printf '%s\n' "$out" | sed '1d'          # the answer -> stdout
