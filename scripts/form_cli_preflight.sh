#!/usr/bin/env bash
# form_cli_preflight.sh — air-gap readiness check for the form-cli.
#
# Proves the offline self-improvement kit is whole: the native fkwu form-cli
# runs, the surface membrane is legible, local grounded RAG is present, the
# stdlib recipes + specs are on disk, and legacy bridge checks are named as
# bridge checks instead of the runtime.
#
# The LOGIC (the surface report) is Form, evaluated on the kernel. This shell is
# a thin carrier: it orchestrates checks and runs the kernel. No body lives here.
# Written for stock macOS bash 3.2 — no mapfile, arrays guarded.
#
# Usage: scripts/form_cli_preflight.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="$ROOT/form/form-kernel-go"
GO="$GO_DIR/bin-go"
MENTOR_MODELS="$HOME/mentor-install/.models"
PASS=0; GAP=0
ok(){ printf "  ✓  %s\n" "$1"; PASS=$((PASS+1)); }
gap(){ printf "  ✗  GAP: %s\n" "$1"; GAP=$((GAP+1)); }
note(){ printf "     %s\n" "$1"; }

echo "── form-cli air-gap preflight ──"

# 1. Kernel: build + eval smoke ------------------------------------------------
echo "[1] Form kernel"
if [[ ! -x "$GO" ]] || find "$GO_DIR" -name '*.go' -newer "$GO" -print -quit 2>/dev/null | grep -q .; then
    ( cd "$GO_DIR" && go build -o bin-go . ) 2>/dev/null
fi
if [[ -x "$GO" ]]; then
    smoke="$("$GO" <(echo "(print (add 20 22))") 2>/dev/null | tr -d '[:space:]')"
    case "$smoke" in 42*) ok "kernel builds and evaluates (20+22=42)" ;; *) gap "kernel built but eval smoke failed (got '$smoke')" ;; esac
else
    gap "kernel did not build — need Go toolchain (offline-fine once built)"
fi

# 2. Surface membrane: Form-native report --------------------------------------
echo "[2] Surface membrane (Form-native)"
if [[ -x "$GO" ]]; then
    rep="$(mktemp)"; trap 'rm -f "$rep"' EXIT
    # The kernel walks the Lisp dialect natively (builtins len/add/eq are native);
    # core.fk is the BML maintenance dialect and needs the source-compiler, so it
    # is NOT preluded here — these three Lisp recipes are all the report needs.
    { cat "$ROOT/form/form-stdlib/tool-channel.fk" \
          "$ROOT/form/form-stdlib/choice-receipt.fk" \
          "$ROOT/form/form-stdlib/form-cli-membrane.fk"
      echo '(print (fcm-surface-protocol-count))'
      echo '(print (fcm-surface-native-count))'
      echo '(print (fcm-surface-host-count))'
    } > "$rep"
    S_PROT=""; S_NAT=""; S_HOST=""; i=0
    while IFS= read -r line; do
        line="$(printf '%s' "$line" | tr -d '[:space:]')"
        [[ -z "$line" || "$line" == "null" ]] && continue
        case $i in 0) S_PROT="$line";; 1) S_NAT="$line";; 2) S_HOST="$line";; esac
        i=$((i+1))
    done < <("$GO" "$rep" 2>/dev/null)
    if [[ -n "$S_PROT" ]] && [[ "$S_PROT" -ge 1 ]] 2>/dev/null; then
        ok "membrane reports $S_PROT channels: $S_NAT native-recipe, $S_HOST host-crossing"
        note "host-crossings are where a native recipe is a gap to close"
    else
        gap "membrane report did not evaluate"
    fi
else
    gap "skipped — kernel unavailable"
fi

# 3. Native form-cli + local model assets --------------------------------------
echo "[3] Native form-cli + model assets"
NATIVE_CLI=""
if [[ -x "$ROOT/form/form-cli" ]]; then
    NATIVE_CLI="$ROOT/form/form-cli"
elif [[ "$(uname -s)-$(uname -m)" == "Darwin-arm64" && -x "$ROOT/form/form-stdlib/bootstrap/form-cli-darwin-arm64" ]]; then
    NATIVE_CLI="$ROOT/form/form-stdlib/bootstrap/form-cli-darwin-arm64"
fi
if [[ -n "$NATIVE_CLI" ]]; then
    ver="$(printf 'version\nquit\n' | "$NATIVE_CLI" 2>/dev/null | head -1)"
    ok "native fkwu form-cli present: $ver"
else
    gap "native fkwu form-cli missing — run scripts/ensure_form_cli_native.sh"
fi
N_GGUF=0; CODER_GGUF=""
if [[ -d "$MENTOR_MODELS" ]]; then
    while IFS= read -r g; do
        [[ -z "$g" ]] && continue
        N_GGUF=$((N_GGUF+1))
        case "$g" in *coder*) CODER_GGUF="$g";; esac
    done < <(find "$MENTOR_MODELS" -maxdepth 1 -iname '*.gguf' 2>/dev/null)
    [[ "$N_GGUF" -gt 0 ]] && ok "GGUF weights on disk: $N_GGUF file(s) in mentor-install/.models"
fi
[[ -n "$CODER_GGUF" ]] && note "coder GGUF available for the fkwu+Metal synthesis lane: $CODER_GGUF"

# 4. Recipes + specs on disk ---------------------------------------------------
echo "[4] Body on disk (recipes + specs)"
FK=$(find "$ROOT/form/form-stdlib" -name '*.fk' 2>/dev/null | grep -c . | tr -d ' ')
SPECS=$(find "$ROOT/specs" -name '*.md' 2>/dev/null | grep -c . | tr -d ' ')
[[ "$FK" -gt 0 ]] && ok "$FK Form stdlib recipes present" || gap "no Form recipes found"
[[ "$SPECS" -gt 0 ]] && ok "$SPECS specs present (idea→form-spec source)" || gap "no specs found"

# 5. Native grounded ask smoke --------------------------------------------------
echo "[5] Native grounded ask"
if [[ -n "$NATIVE_CLI" ]]; then
    mkdir -p "$HOME/.coherence-network"
    printf 'substrate' > "$HOME/.coherence-network/rag-query.txt"
    ask_out="$(cd "$HOME" && printf 'ask-staged\nquit\n' | "$NATIVE_CLI" 2>/dev/null)"
    if printf '%s' "$ask_out" | grep -q '^grounded:'; then
        ok "native staged ask returns a grounded RAG cell"
    else
        gap "native ask did not return a grounded cell"
    fi
else
    gap "skipped — native form-cli unavailable"
fi

# 6. Offline semantic memory (RAG over the body) ------------------------------
echo "[6] Offline semantic memory (RAG)"
RAG_INDEX="$HOME/.coherence-network/rag-index/index.jsonl"
RAG_N=0; [[ -f "$RAG_INDEX" ]] && RAG_N=$(grep -c . "$RAG_INDEX" 2>/dev/null | tr -d ' ')
if [[ "$RAG_N" -gt 0 ]]; then
    ok "RAG index: $RAG_N cells present for fkwu rag-ask.fk"
else
    gap "no offline memory — run the startup RAG/index setup before agent work"
fi

# 7. Synthesis lane receipt -----------------------------------------------------
echo "[7] Native synthesis lane"
if [[ -n "$NATIVE_CLI" ]]; then
    synth_out="$(cd "$HOME" && printf 'synthesis-status\nquit\n' | "$NATIVE_CLI" 2>/dev/null)"
    if printf '%s' "$synth_out" | grep -q '^synthesis-lane:fkwu-metal-answer-bound' &&
       printf '%s' "$synth_out" | grep -q '^missing:none'; then
        ok "synthesis lane binds decoded local answers"
        note "full-width real-GGUF semantic generation remains a named upgrade, not a hidden HTTP oracle"
    else
        gap "synthesis lane did not return a decoded-answer binding receipt"
    fi
else
    gap "skipped — native form-cli unavailable"
fi

# 8. Readiness receipt ---------------------------------------------------------
echo "── receipt ──"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
VERDICT="READY"; [[ "$GAP" -gt 0 ]] && VERDICT="GAPS:$GAP"
printf "  when      %s\n  checks    %d passed, %d gap(s)\n  native    %s\n  gguf      %s\n  verdict   %s\n" \
    "$STAMP" "$PASS" "$GAP" "${NATIVE_CLI:-missing}" "${N_GGUF:-0}" "$VERDICT"
if [[ "$GAP" -eq 0 ]]; then
    echo "  the grounded kit is whole — you can lose the network and keep improving."
    echo "  decoded answer binding is local; full-width semantic generation is still an explicit upgrade."
else
    echo "  close the gaps above before the network goes dark."
fi
[[ "$GAP" -eq 0 ]]
