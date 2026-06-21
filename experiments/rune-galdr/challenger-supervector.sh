#!/usr/bin/env bash
# challenger-supervector.sh — Challenger 1 ("Stat") feature carrier.
#
# Extract a clip's 20-band mel-ish frames (sox filterbank) and pool them with the Form body
# (speaker-stat.fk: ss-supervector) into a 40-d speaker supervector (mean ++ mad). The
# pooling MODEL is Form; this carrier only measures the bands. Print = space-separated ints.
#
#   challenger-supervector.sh clip.wav
# Run under bash (zsh mangles the band array). Compare challengers vs the ECAPA champion with
# the cosine of two supervectors (see README).
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../form"
K=form-kernel-rust/target/release/form-kernel-rust
V="${1:?clip.wav}"
edges=(80 160 240 340 460 600 760 950 1170 1420 1710 2040 2410 2830 3300 3830 4420 5080 5810 6620 7600)
frame_of() { local t="$1" out="" i lo hi e
  for ((i=0;i<20;i++)); do lo=${edges[i]}; hi=${edges[i+1]}
    e=$(sox "$V" -n trim "$t" 1.5 highpass 60 sinc "${lo}"-"${hi}" stat 2>&1 | awk '/RMS +amplitude/{printf "%d",$3*1000+0.5}')
    out="$out ${e:-0}"; done; echo "${out# }"; }
frames=""
for t in 1 3 5 7 9 11 13 15; do frames="$frames (list $(frame_of "$t"))"; done
echo "(do (print (ss-supervector (list $frames))))" > /tmp/cs-$$.fk
"$K" form-stdlib/speaker-stat.fk /tmp/cs-$$.fk 2>/dev/null | grep -E '^\[' | tr -d '[]' | tr ',' ' '
rm -f /tmp/cs-$$.fk
