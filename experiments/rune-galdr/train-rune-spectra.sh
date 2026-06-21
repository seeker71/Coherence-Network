#!/usr/bin/env bash
# train-rune-spectra.sh — the CARRIER that gives each Elder Futhark rune its galdr
# "vibration": synthesize the rune's sustained sound, extract a 6-band spectral
# signature with sox, and emit Form table rows for form-stdlib/nordic-runes.fk.
#
# This is physical I/O + DSP only (carrier-last). The MODEL — the rune table and the
# symbol<->spectrum flow-match — lives in Form (nordic-runes.fk, rune-frequency.fk).
# A rune's "frequency" here is the honest acoustic spectrum of its sung phoneme
# (formant/fricative energy per band), NOT a mystical single-Hz attribution.
#
# Run:  train-rune-spectra.sh            # prints the spectral table + Form rows
#       VOICE=Daniel RATE=110 train-rune-spectra.sh
set -uo pipefail
VOICE="${VOICE:-Daniel}"; RATE="${RATE:-110}"
TMP=/tmp/rune-train; mkdir -p "$TMP"

# 24 Elder Futhark runes: glyph | name | phoneme | aett(1-3) | keyword | sustained galdr sound
RUNES=(
"ᚠ|fehu|f|1|wealth|ffffffeh"
"ᚢ|uruz|u|1|strength|ooooooo"
"ᚦ|thurisaz|th|1|thorn|ththththh"
"ᚨ|ansuz|a|1|breath-god|aaaaaaa"
"ᚱ|raidho|r|1|journey|rrrrrrr"
"ᚲ|kenaz|k|1|torch|kehkehkeh"
"ᚷ|gebo|g|1|gift|gehgehgeh"
"ᚹ|wunjo|w|1|joy|wuuuuuu"
"ᚺ|hagalaz|h|2|hail|hahhahah"
"ᚾ|nauthiz|n|2|need|nnnnnnn"
"ᛁ|isa|i|2|ice|iiiiiii"
"ᛃ|jera|y|2|harvest|yehyehyeh"
"ᛇ|eihwaz|ei|2|yew|eyeyeyey"
"ᛈ|perthro|p|2|fate-lot|pehpehpeh"
"ᛉ|algiz|z|2|protection|zzzzzzz"
"ᛋ|sowilo|s|2|sun|sssssss"
"ᛏ|tiwaz|t|3|justice|tehtehteh"
"ᛒ|berkano|b|3|birch-birth|behbehbeh"
"ᛖ|ehwaz|e|3|horse|eeeeeee"
"ᛗ|mannaz|m|3|human|mmmmmmm"
"ᛚ|laguz|l|3|water|llllllll"
"ᛜ|ingwaz|ng|3|seed|ngngngng"
"ᛟ|othala|o|3|home-dna|oooohhh"
"ᛞ|dagaz|d|3|day-dawn|dehdehdeh"
)

# raw band energy = RMS*10000 in a sub-band. Bands sit in the VOCAL FORMANT range,
# above a frame drum's ~80-100 Hz fundamental and worst harmonics, so the galdr's
# formant contour — not the drum — shapes the signature (voice-isolation front-end).
band_rms() { sox "$1" -n highpass 80 sinc "$2"-"$3" stat 2>&1 | awk '/RMS +amplitude/{printf "%d",$3*10000+0.5}'; }
# the six formant bands (Hz), shared by training and matching:
FB=(250 450  450 700  700 1100  1100 1700  1700 2600  2600 4000)

echo "; nordic-rune spectral signatures (peak-normalized SHAPE 0..9) — VOICE=$VOICE RATE=$RATE"
printf "; %-9s %2s %2s %2s %2s %2s %2s\n" rune b0 b1 b2 b3 b4 b5 >&2
for r in "${RUNES[@]}"; do
  IFS='|' read -r glyph name ph aett kw snd <<<"$r"
  say -v "$VOICE" -r "$RATE" -o "$TMP/r.aiff" "$snd" 2>/dev/null
  sox "$TMP/r.aiff" -c 1 -r 16000 "$TMP/r.wav" 2>/dev/null
  raw=( $(band_rms "$TMP/r.wav" "${FB[0]}" "${FB[1]}") $(band_rms "$TMP/r.wav" "${FB[2]}" "${FB[3]}") \
        $(band_rms "$TMP/r.wav" "${FB[4]}" "${FB[5]}") $(band_rms "$TMP/r.wav" "${FB[6]}" "${FB[7]}") \
        $(band_rms "$TMP/r.wav" "${FB[8]}" "${FB[9]}") $(band_rms "$TMP/r.wav" "${FB[10]}" "${FB[11]}") )
  # peak-normalize to SHAPE: each band -> round(9 * band / max)
  max=0; for v in "${raw[@]}"; do [[ ${v:-0} -gt $max ]] && max=$v; done; [[ $max -eq 0 ]] && max=1
  q=(); for v in "${raw[@]}"; do q+=( $(( (${v:-0}*9 + max/2) / max )) ); done
  printf "; %-9s %2s %2s %2s %2s %2s %2s\n" "$name" "${q[@]}" >&2
  echo "        (rune \"$glyph\" \"$name\" \"$ph\" $aett \"$kw\" (list ${q[*]}))"
done
rm -rf "$TMP"
