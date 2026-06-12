#!/usr/bin/env bash
# meeting_companion.sh — a meeting companion that LISTENS (STT), DECIDES whether
# it was addressed (a Hati-OS-compiled binary, the Form decision cell), and
# when asked, ANSWERS with an LLM and SPEAKS the reply (TTS).
#
# The body honored: the heavy compute rides host organs the 4th kernel drives —
#   STT  = whisper-cli / whisper-stream (whisper.cpp, large-v3-turbo) on the mic
#   LLM  = ollama on the GPU (Metal)
#   TTS  = /usr/bin/say
# The DECISION — "was the companion addressed? what is the question?" — is Form:
# scripts builds a wake-word matcher (form-stdlib/hati-os-match.fk) emitted by the
# Go kernel and compiled by clang into fkmatch; that Hati-OS binary scans each
# transcript segment over the BMF cursor and answers 1/0. The orchestration glue
# below is an honest CARRIER, to be lifted into Form as the walker grows the op
# families (file/loop) — named, not hidden.
#
# Run it tomorrow:
#   scripts/meeting_companion.sh                 # wake word "kernel", large-v3-turbo
#   WAKE=companion MODEL=~/whisper-models/ggml-large-v3-turbo.bin scripts/meeting_companion.sh
# Speak; when you say the wake word in a sentence, it answers that sentence aloud.
# Ctrl-C to stop. A full transcript is written to the meeting log.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"
WAKE="${WAKE:-kernel}"
MODEL="${MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"
LLM="${LLM:-llama3.2:3b}"
WORK="${WORK:-$HOME/.coherence-meeting}"
mkdir -p "$WORK"
LOG="$WORK/transcript-$(date +%Y%m%d-%H%M%S).txt"

need() { command -v "$1" >/dev/null || { echo "FAIL: missing '$1' — $2"; exit 1; }; }
need "$CLANG" "a C toolchain"
need whisper-stream "brew install whisper-cpp"
need ollama "brew install ollama; ollama pull $LLM"
need say "macOS TTS (built in)"
[[ -f "$MODEL" ]] || { echo "FAIL: whisper model not at $MODEL — download ggml-large-v3-turbo.bin"; exit 1; }
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)

# ── build the Hati-OS wake-word matcher (the Form decision cell) ──────
echo "building the Hati-OS wake-word matcher for '$WAKE'..."
DRV="$WORK/match-driver.fk"
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/hati-os-kernel.fk" \
    "$FORMDIR/form-stdlib/hati-os-kernel-emit.fk" "$FORMDIR/form-stdlib/hati-os-match.fk" > "$DRV"
printf '(print "==M==")\n(print (fkc-emit-driver (fm-contains-fns "%s")))\n(print "==END==")\n' "$WAKE" >> "$DRV"
(cd "$FORMDIR" && "$GO_BIN" "$DRV" 2>/dev/null) > "$WORK/match.out"
sed -n '/^==M==$/,/^==END==$/p' "$WORK/match.out" | sed -e '1d' -e '$d' > "$WORK/fkmatch.c"
"$CLANG" -O2 -o "$WORK/fkmatch" "$WORK/fkmatch.c"
FKMATCH="$WORK/fkmatch"
echo "  fkmatch ready (a binary the 4th kernel compiled; scans each segment over the BMF cursor)"

echo "listening (wake word: '$WAKE', STT: $(basename "$MODEL"), LLM: $LLM on GPU). Ctrl-C to stop."
echo "transcript -> $LOG"
echo

# recent rolling context for the LLM (last few segments)
CTX=""
# ── listen: whisper-stream emits transcript segments on stdout ───────────
whisper-stream -m "$MODEL" --step 0 --length 8000 -vth 0.6 2>/dev/null | while IFS= read -r line; do
    seg="$(printf '%s' "$line" | sed -E 's/^\[[^]]*\][[:space:]]*//; s/^[[:space:]]+//')"
    [[ -z "$seg" ]] && continue
    case "$seg" in [* ) continue;; esac
    printf '%s\n' "$seg" >> "$LOG"
    CTX="$(printf '%s\n%s' "$CTX" "$seg" | tail -8)"
    # the Hati-OS binary decides: was the companion addressed?
    if [[ "$("$FKMATCH" echo "$seg" 2>/dev/null | head -1)" == "1" ]]; then
        echo "  [addressed] $seg"
        prompt="You are a meeting companion. Recent transcript:
$CTX

The participant addressed you (wake word '$WAKE'). Answer their request in 1-2 spoken sentences, concise and useful."
        reply="$(printf '%s' "$prompt" | ollama run "$LLM" 2>/dev/null | tr '\n' ' ' | sed 's/  */ /g')"
        [[ -z "$reply" ]] && reply="I heard you, but I do not have an answer yet."
        echo "  [reply] $reply"
        printf '>> %s\n' "$reply" >> "$LOG"
        say "$reply"
    fi
done
