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
GUIDE=""
if [[ "${FNR_NO_GUIDE:-0}" != "1" && -f "$STD/form-cli-predict.fk" ]]; then
    # task keywords (lowercase 4+ letter words, deduped)
    kw="$(printf '%s' "$TASK" | tr 'A-Z' 'a-z' | grep -oE '[a-z]{4,}' | awk '!s[$0]++' | head -12 | sed 's/.*/"&"/' | tr '\n' ' ')"
    { cat "$STD/form-cli-predict.fk" "$STD/form-cli-model.fk"
      echo '(let base (fpm-base))'
      echo '(let boosts (fpm-boosts))'
      echo "(let kw (list ${kw:-\"\"}))"
      for t in Bash Read Write Edit Grep Glob Agent; do echo "(print (fcp-predicted? base boosts kw \"$t\" (fpm-threshold) (fpm-boost-amt)))"; done
    } > "$work/predict.fk"
    # map predictor tools -> the runner's tool vocabulary (bash/read_file/write_file/search)
    j=0; runner_tools=""
    while IFS= read -r v; do
        j=$((j+1)); pt=$(echo "Bash Read Write Edit Grep Glob Agent" | cut -d' ' -f$j)
        [[ "$(printf '%s' "$v" | tr -d '[:space:]')" == "1" ]] || continue
        case "$pt" in
            Bash) runner_tools="$runner_tools bash";;
            Read) runner_tools="$runner_tools read_file";;
            Write|Edit) runner_tools="$runner_tools write_file";;
            Grep|Glob) runner_tools="$runner_tools search";;
        esac
    done < <("$GO" "$work/predict.fk" 2>/dev/null | head -7)
    runner_tools="$(printf '%s\n' $runner_tools | awk '!s[$0]++' | tr '\n' ' ' | sed 's/ *$//')"
    [[ -n "$runner_tools" ]] && GUIDE="GUIDANCE: similar past tasks needed these tools — reach for them when relevant: ${runner_tools// /, }.\n\n"
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
