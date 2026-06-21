#!/usr/bin/env bash
# rune-galdr.sh — the live symbol<->frequency flow-match carrier.
#
# Hear a galdr (from the mic, a synthesized sound, or a clip of a recording), extract
# its 6-band spectral SHAPE with sox, and ask the Form body (rune-frequency.fk over
# nordic-runes.fk) which Elder Futhark rune it is. Carrier = physical I/O + DSP only;
# the match decision is the four-way-proven Form recipe's.
#
#   rune-galdr.sh --say "ssssss"            # synthesize a sound, name its rune
#   rune-galdr.sh --wav file.wav [START DUR] # name the rune in a recording clip
#   rune-galdr.sh --listen [SECONDS]         # record the mic, name the rune
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORM="$(cd "$SCRIPT_DIR/../.." && pwd)/form"
KERNEL="$FORM/form-kernel-rust/target/release/form-kernel-rust"
[[ -x "$KERNEL" ]] || { echo "FAIL no kernel — run: (cd $FORM && ./validate.sh form-stdlib/core.fk form-stdlib/nordic-runes.fk form-stdlib/rune-frequency.fk form-stdlib/tests/rune-frequency-band.fk)"; exit 1; }
TMP=/tmp/rune-galdr.$$; mkdir -p "$TMP"; trap 'rm -rf "$TMP"' EXIT

band() { sox "$1" -n highpass 80 sinc "$2"-"$3" stat 2>&1 | awk '/RMS +amplitude/{printf "%d",$3*10000+0.5}'; }
# 6-band peak-normalized SHAPE (0..9) — identical recipe to train-rune-spectra.sh
spectrum() {  # $1 wav -> "b0 b1 b2 b3 b4 b5"
  local w="$1"
  local r=( $(band "$w" 20 200) $(band "$w" 200 500) $(band "$w" 500 1000) \
            $(band "$w" 1000 2000) $(band "$w" 2000 4000) $(band "$w" 4000 7900) )
  local max=0 v; for v in "${r[@]}"; do [[ ${v:-0} -gt $max ]] && max=$v; done; [[ $max -eq 0 ]] && max=1
  local q=(); for v in "${r[@]}"; do q+=( $(( (${v:-0}*9 + max/2) / max )) ); done
  echo "${q[*]}"
}
identify() {  # $1 wav -> prints the matched rune via the Form body
  local spec; spec="$(spectrum "$1")"
  local drv="$TMP/q.fk"
  cat > "$drv" <<FK
(do (print (list "spectrum" (list $spec)
            "rune" (rf-match (list $spec))
            "glyph" (rf-glyph (list $spec))
            "aett" (rf-aett (list $spec))
            "confidence" (rf-confidence (list $spec)))))
FK
  ( cd "$FORM" && "$KERNEL" form-stdlib/nordic-runes.fk form-stdlib/rune-frequency.fk "$drv" 2>/dev/null | grep -E '^\[' | tail -1 )
}

case "${1:-}" in
  --say)
    say -v "${VOICE:-Daniel}" -r "${RATE:-110}" -o "$TMP/s.aiff" "${2:?need a sound}" 2>/dev/null
    sox "$TMP/s.aiff" -c 1 -r 16000 "$TMP/s.wav" 2>/dev/null
    identify "$TMP/s.wav" ;;
  --wav)
    src="${2:?need a wav/mp3}"; start="${3:-0}"; dur="${4:-8}"
    sox "$src" -c 1 -r 16000 "$TMP/s.wav" trim "$start" "$dur" 2>/dev/null
    identify "$TMP/s.wav" ;;
  --listen)
    secs="${2:-6}"; echo "[rune-galdr] listening ${secs}s — gall a rune now…"
    rec -q -c 1 -r 16000 "$TMP/s.wav" trim 0 "$secs" >/dev/null 2>&1 || { echo "mic unavailable (grant Microphone)"; exit 2; }
    identify "$TMP/s.wav" ;;
  *) sed -n '8,11p' "$0" | sed 's/^# *//' ;;
esac
