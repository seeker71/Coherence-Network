#!/usr/bin/env bash
# logmel-supervector.sh — the LOG-MEL feature front-end for the speaker challengers.
#
# Replaces the coarse 20-band sox supervector with whisper's own 80-dim log-mel, computed by the
# four-way-proven Form recipe (mfu-col over mel-filterbank.fk's Slaney bank). For each of N frames
# (hop 0.5 s, 400-sample window) it calls the Form log-mel column, then pools per-band mean ++ std
# into a 160-d supervector. CMVN/centering is a scoring-step concern (speaker-proj sl-center).
#
# The recipe is the body; this carrier only reads samples + pools. Honest floor: the tree-walker
# does ~0.8 s per 80-row column, so this is demo-scale — the full corpus wants the native (emit→asm)
# lane the mel recipe was built for ("JIT for throughput").
#
#   logmel-supervector.sh clip.wav            -> 160 floats (mean[80] ++ std[80])
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../form"
K=form-kernel-rust/target/release/form-kernel-rust
PRE="form-stdlib/trig.fk form-stdlib/mel-frame.fk form-stdlib/mel-full.fk form-stdlib/mel-filterbank.fk"
W="${1:?clip.wav (16k mono)}"; TMP=$(mktemp /tmp/lm.XXXX.fk)
col(){ python3 - "$W" "$1" <<'PY' > "$TMP"
import wave,array,sys
w=wave.open(sys.argv[1],'rb'); w.setpos(int(float(sys.argv[2])*16000)); a=array.array('h'); a.frombytes(w.readframes(400))
print("(do (print (mfu-col (list "+" ".join(f"{x/32768.0:.6f}" for x in a)+") (melbank) 400)))")
PY
  $K $PRE "$TMP" 2>/dev/null | grep -E '^\[' | tr -d '[]' | tr ',' ' '; }
: > "$TMP.cols"
for t in 1.0 1.5 2.0 2.5 3.0 3.5 4.0 4.5 5.0 5.5; do col "$t" >> "$TMP.cols"; done
awk '{for(i=1;i<=NF;i++){s[i]+=$i;q[i]+=$i*$i;n[i]++}}
     END{for(i=1;i<=80;i++)printf "%.5f ",s[i]/n[i]; for(i=1;i<=80;i++){m=s[i]/n[i];v=q[i]/n[i]-m*m;if(v<0)v=0;printf "%.5f ",sqrt(v)}}' "$TMP.cols"
echo; rm -f "$TMP" "$TMP.cols"
