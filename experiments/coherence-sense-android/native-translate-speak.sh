#!/usr/bin/env bash
# native-translate-speak.sh — the live rung: a Form-NATIVE NL->NL translate stage
# wired between the STT and TTS oracles, the first place the speech loop shows a
# Form-native translation running end to end.
#
# BML-first: the LOGIC is Form — form-stdlib/nl-translate.fk, four-way proven by
# tests/nl-translate-band.fk (witness 31, Go/Rust/TS/fkwu). THIS carrier is thin
# host-IO only: build the input program, run the kernel, speak the result, write a
# receipt. The kernel call is one line; every translation decision lives in Form.
#
# Usage:
#   native-translate-speak.sh "the source is native"          # en -> id, say it
#   native-translate-speak.sh "sumber adalah asli" id-en      # id -> en
#   native-translate-speak.sh --voice "the kernel is native"  # full voice -> voice:
#     say(en) -> wav -> whisper-cli transcribe (STT oracle) -> NATIVE translate
#     -> say (TTS oracle). The native middle is the only non-oracle stage.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && GOPROXY=off go build -o bin-go . ) >/dev/null 2>&1
[[ -x "$GO" ]] || { echo "FAIL no Form kernel (bin-go) — build: (cd $ROOT/form/form-kernel-go && go build -o bin-go .)"; exit 1; }
# core.fk is the only source-compiled prelude; nl-translate's deps are all builtins
# + already-low-level cells, so the native translate runs without it.
PRELUDE=(json cache form-ontology-loader line-grammar bmf-core bmf-grammar string-case nl-translate)
SRCS=(); for p in "${PRELUDE[@]}"; do SRCS+=("$STD/$p.fk"); done

# native translate: ONE kernel call, all logic is Form. dir = en-id | id-en
translate() {  # $1 text  $2 dir -> stdout target surface
  local fn="tr-en-id"; [[ "${2:-en-id}" == "id-en" ]] && fn="tr-id-en"
  local esc="${1//\"/}"   # the grammar tokenizes on whitespace; drop stray quotes
  local run; run="$(mktemp)"; printf '(do (print (%s "%s")) 0)\n' "$fn" "$esc" > "$run"
  "$GO" "${SRCS[@]}" "$run" 2>/dev/null | grep -vE '^0$' | head -1
  rm -f "$run"
}

MODE="text"; [[ "${1:-}" == "--voice" ]] && { MODE="voice"; shift; }
TEXT="${1:?usage: native-translate-speak.sh [--voice] \"text\" [en-id|id-en]}"
DIR="${2:-en-id}"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ "$MODE" == "voice" ]]; then
  MODEL="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"
  wav="$(mktemp).wav"; aiff="$(mktemp).aiff"
  say -o "$aiff" "$TEXT" 2>/dev/null && sox "$aiff" -c 1 -r 16000 "$wav" 2>/dev/null
  if command -v whisper-cli >/dev/null && [[ -f "$MODEL" ]]; then
    of="$(mktemp)"; whisper-cli -m "$MODEL" -f "$wav" -nt -oj -of "$of" -t 4 -l en >/dev/null 2>&1
    TEXT="$(jq -r '[.transcription[].text]|join(" ")|gsub("^\\s+|\\s+$";"")' "$of.json" 2>/dev/null)"
    echo "[stt-oracle whisper-cli] heard: \"$TEXT\""
  else
    echo "[stt-oracle absent — translating the text input directly]"
  fi
  rm -f "$wav" "$aiff"
fi

# surface normalization (case, punctuation) is now owned by the Form ENCODER
# (str-normalize in form-stdlib/string-case.fk) — no shell cleaning here.
OUT="$(translate "$TEXT" "$DIR")"
echo "[native-translate · form-stdlib/nl-translate.fk · $DIR]  \"$TEXT\"  ->  \"$OUT\""
if command -v say >/dev/null; then say "$OUT" 2>/dev/null && echo "[tts-oracle say] spoke the translation"; fi

REC="$ROOT/experiments/coherence-sense-android/.native-translate-receipt.json"
printf '{"ts":"%s","stage":"nl-native-translate","dir":"%s","input":"%s","output":"%s","body":"form-stdlib/nl-translate.fk","kernel":"form-kernel-go","stt":"whisper-cli(oracle)","tts":"say(oracle)","native_middle":true}\n' \
  "$TS" "$DIR" "$TEXT" "$OUT" > "$REC"
echo "[receipt] $REC"
