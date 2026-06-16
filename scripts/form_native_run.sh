#!/usr/bin/env bash
# form_native_run.sh — run the PURE FORM agent runner (form-stdlib/form-native-run.fk)
# via the kernel. No C, no Python in the body; host effects via the kernel's host-io.
#
# The runner SELF-GUIDES: before the loop it consults the corpus-trained tool
# predictor (form-cli-predict.fk) for the tools this task will likely need, maps
# them to the runner's tool vocabulary, and feeds them to the loop via
# fnr-run-guided — so the local model stops omitting tools it learned to need
# (e.g. bash). The guidance is computed in Form; this shell wires it. Set
# FNR_NO_GUIDE=1 for the bare unguided runner.
#
# Usage: form_native_run.sh "<task>" "<oracle-cmd>" [max-steps]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
[[ -x "$GO" ]] || (cd "$ROOT/form/form-kernel-go" && go build -o bin-go .)
TASK="${1:?task}"; ORACLE="${2:-ollama run qwen2.5:72b}"; MAX="${3:-8}"
esc(){ printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

# ── self-guidance: ask the trained predictor which tools this task needs ──
# The whole self-guidance is Form now: text-tokenize.fk lowercases and splits the
# task into keywords (char_at + ord, four-way), form-cli-predict/-model/-guide map
# and assemble the hint. The carrier only splits the tokenizer's space-joined
# result, dedups, and quotes it into the keyword list — data-munging, not logic.
GUIDE=""
if [[ "${FNR_NO_GUIDE:-0}" != "1" && -f "$STD/form-cli-guide.fk" ]]; then
    { cat "$STD/text-tokenize.fk"; echo "(print (tk-words \"$(esc "$TASK")\" 4))"; } > "$work/tok.fk"
    words="$("$GO" "$work/tok.fk" 2>/dev/null | sed '/^null$/d' | head -1)"
    kw="$(printf '%s' "$words" | tr ' ' '\n' | awk 'NF && !s[$0]++' | head -12 | sed 's/.*/"&"/' | tr '\n' ' ')"
    { cat "$STD/form-cli-predict.fk" "$STD/form-cli-model.fk" "$STD/form-cli-guide.fk"
      echo "(print (fcg-guide (fpm-base) (fpm-boosts) (list ${kw:-\"\"}) (fpm-threshold) (fpm-boost-amt)))"
    } > "$work/guide.fk"
    g="$("$GO" "$work/guide.fk" 2>/dev/null | sed '/^null$/d' | head -1)"
    [[ -n "$g" && "$g" != "null" ]] && GUIDE="$g\n\n"
fi

{ cat "$STD/form-native-run.fk"
  if [[ -n "$GUIDE" ]]; then
      echo "(print (fnr-run-guided \"$(esc "$TASK")\" \"$(esc "$ORACLE")\" $MAX \"$(esc "$GUIDE")\"))"
  else
      echo "(print (fnr-run \"$(esc "$TASK")\" \"$(esc "$ORACLE")\" $MAX))"
  fi
} > "$work/run.fk"
[[ -n "$GUIDE" ]] && printf '  [self-guided: %s]\n' "${GUIDE%%.*}" >&2
"$GO" "$work/run.fk"
