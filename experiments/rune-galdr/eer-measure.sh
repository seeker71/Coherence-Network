#!/usr/bin/env bash
# eer-measure.sh — feed real verification trials through eer.fk (the four-way Form metric), at scale.
#
# Instrument upgrade (post first-EER, on the Grok/Cursor panel's advice):
#   - SEGMENT-TRIAL GENERATOR: each ceremony voice → 8 short crops (not 2 windows) → ~276 trials
#     (84 genuine same-speaker + 192 impostor cross-speaker), so EER is finely resolved, not quantized.
#   - POOLING DECOMPOSITION: mean-only / std-only / mean+std. Grok flagged that the std dims of a
#     mean+std supervector mostly track NUISANCE (channel/breath/energy), not identity — and that
#     per-utterance CMVN (zeroing each segment's frame-mean) reduces mean+std to exactly std-only.
#     So this sweep IS the test: if mean-only beats std-only, the std half is nuisance.
#   - BOOTSTRAP CI: resample the trials B times → EER median + [5th,95th] percentile, so we report a
#     stable interval, not one fragile point (Cursor's caution).
# The metric (eer.fk) is the Form body; this carrier assembles trials + sweeps pooling to FIND the
# winner (which then earns a Form recipe). Recordings/roster stay private; only the numbers leave.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../form"
K=form-kernel-rust/target/release/form-kernel-rust
PRE="form-stdlib/trig.fk form-stdlib/mel-frame.fk form-stdlib/mel-full.fk form-stdlib/mel-filterbank.fk"
SEP=~/.coherence-network/recordings/speakers/sep/htdemucs
B="${1:-60}"   # bootstrap resamples
col(){ python3 - "$1" "$2" <<'PY'
import wave,array,sys
w=wave.open(sys.argv[1],'rb'); w.setpos(int(float(sys.argv[2])*16000)); a=array.array('h'); a.frombytes(w.readframes(400))
print("(do (print (mfu-col (list "+" ".join(f"{x/32768.0:.6f}" for x in a)+") (melbank) 400)))")
PY
}
spk=(ubbe brigitte angelia); offs=(1.0 2.5 4.0 5.5 7.0 8.5 10.0 11.5)   # 3 voices x 8 crops = 24 segments
echo "extracting log-mel: 24 segments x 4 frames (~77s on the tree-walker)..."
si=0; declare -a SEGSPK
for s in 0 1 2; do for o in "${offs[@]}"; do : > /tmp/seg_$si.fr; SEGSPK[$si]=$s
  for d in 0.0 0.4 0.8 1.2; do t=$(awk "BEGIN{print $o+$d}")
    col "$SEP/${spk[s]}.16k/vocals.wav" "$t" > /tmp/seg_col.fk
    $K $PRE /tmp/seg_col.fk 2>/dev/null | grep -E '^\[' | tr -d '[]' | tr ',' ' ' >> /tmp/seg_$si.fr; done
  si=$((si+1)); done; done
N=$si
pool(){ awk -v m="$1" '{for(i=1;i<=NF;i++){s[i]+=$i;q[i]+=$i*$i;n[i]++}}
  END{for(i=1;i<=80;i++){mu=s[i]/n[i];v=q[i]/n[i]-mu*mu;if(v<0)v=0;sd=sqrt(v);
        if(m=="mean")printf "%.5f ",mu; else if(m=="std")printf "%.5f ",sd; else printf "%.5f ",mu}
      if(m=="both"){for(i=1;i<=80;i++){mu=s[i]/n[i];v=q[i]/n[i]-mu*mu;if(v<0)v=0;printf "%.5f ",sqrt(v)}}}' "/tmp/seg_$2.fr"; }
cosv(){ paste -d' ' <(echo "$1") <(echo "$2")|awk '{n=NF/2;d=0;a=0;b=0;for(i=1;i<=n;i++){d+=$i*$(i+n);a+=$i*$i;b+=$(i+n)*$(i+n)}printf "%.5f",d/(sqrt(a)*sqrt(b)+1e-9)}'; }
run_eer(){ echo "(do (print (eer (list $1))))" > /tmp/seg_eer.fk
  $K form-stdlib/transformer-numerics.fk form-stdlib/eer.fk /tmp/seg_eer.fk 2>/dev/null | grep -E '^-?[0-9]' | tail -1; }
# build trial file "score label" for a pooling mode, return path + the eer.fk list
build(){ local mode="$1" i j; declare -a P
  for ((i=0;i<N;i++)); do P[$i]=$(pool "$mode" $i); done
  : > /tmp/tr_$mode.txt
  for ((i=0;i<N;i++)); do for ((j=i+1;j<N;j++)); do
    [ "${SEGSPK[$i]}" = "${SEGSPK[$j]}" ] && lab=1.0 || lab=0.0
    echo "$(cosv "${P[$i]}" "${P[$j]}") $lab" >> /tmp/tr_$mode.txt; done; done; }
listify(){ awk '{printf "(list %s %s) ",$1,$2}' "$1"; }
boot(){ # bootstrap EER: B resamples with replacement -> median, p5, p95
  local f="$1" b; : > /tmp/boot.txt
  for ((b=1;b<=B;b++)); do
    awk -v seed=$b 'BEGIN{srand(seed)}{a[NR]=$0;n=NR}END{for(i=1;i<=n;i++){r=int(rand()*n)+1;split(a[r],p," ");printf "(list %s %s) ",p[1],p[2]}}' "$f" > /tmp/boot_list.txt
    run_eer "$(cat /tmp/boot_list.txt)" >> /tmp/boot.txt; done
  sort -n /tmp/boot.txt | awk -v B=$B '{v[NR]=$1}END{printf "median=%.3f  [p5=%.3f, p95=%.3f]", v[int(B*0.5)], v[int(B*0.05)+1], v[int(B*0.95)]}'; }
echo; echo "$N segments → $(( N*(N-1)/2 )) trials. EER per pooling (0=perfect, 0.5=chance), eer.fk + bootstrap CI (B=$B):"
for mode in mean std both; do
  build "$mode"
  ngen=$(awk '$2==1.0' /tmp/tr_$mode.txt | wc -l | tr -d ' ')
  printf "  %-10s  EER=%s   %s   (%s genuine trials)\n" "$mode" "$(run_eer "$(listify /tmp/tr_$mode.txt)")" "$(boot /tmp/tr_$mode.txt)" "$ngen"
done
rm -f /tmp/seg_*.fr /tmp/seg_col.fk /tmp/seg_eer.fk /tmp/tr_*.txt /tmp/boot*.txt /tmp/boot_list.txt
