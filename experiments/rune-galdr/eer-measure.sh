#!/usr/bin/env bash
# eer-measure.sh — feed real verification trials through eer.fk (the four-way Form metric).
#
# Builds a trial matrix from the ceremony voices: each speaker's vocal split into two time-windows
# (two "utterances" of the same speaker) → genuine pairs (same speaker) + impostor pairs (cross).
# Scores each pair by cosine of its log-mel supervector, RAW vs +CMVN, and reports EER (eer.fk) for
# each — one comparable number per front-end. The metric is the Form body; this carrier only assembles
# trials. Recordings/roster stay private; only the numbers leave.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../../form"
K=form-kernel-rust/target/release/form-kernel-rust
PRE="form-stdlib/trig.fk form-stdlib/mel-frame.fk form-stdlib/mel-full.fk form-stdlib/mel-filterbank.fk"
SEP=~/.coherence-network/recordings/speakers/sep/htdemucs
col(){ python3 - "$1" "$2" <<'PY'
import wave,array,sys
w=wave.open(sys.argv[1],'rb'); w.setpos(int(float(sys.argv[2])*16000)); a=array.array('h'); a.frombytes(w.readframes(400))
print("(do (print (mfu-col (list "+" ".join(f"{x/32768.0:.6f}" for x in a)+") (melbank) 400)))")
PY
}
# 6 windows: spk0={w0,w1} spk1={w2,w3} spk2={w4,w5}; genuine=(0,1)(2,3)(4,5), else impostor
names=(ubbe ubbe brigitte brigitte angelia angelia); starts=(1.0 5.0 1.0 5.0 1.0 5.0)
echo "extracting log-mel frames for 6 windows (3 voices x 2 time-windows)..."
for i in 0 1 2 3 4 5; do : > /tmp/em_$i.fr
  for off in 0.0 0.4 0.8 1.2 1.6 2.0; do
    t=$(awk "BEGIN{print ${starts[i]}+$off}")
    col "$SEP/${names[i]}.16k/vocals.wav" "$t" > /tmp/em_col.fk
    $K $PRE /tmp/em_col.fk 2>/dev/null | grep -E '^\[' | tr -d '[]' | tr ',' ' ' >> /tmp/em_$i.fr
  done
done
cat /tmp/em_0.fr /tmp/em_1.fr /tmp/em_2.fr /tmp/em_3.fr /tmp/em_4.fr /tmp/em_5.fr > /tmp/em_all.fr
GM=$(awk '{for(i=1;i<=NF;i++){s[i]+=$i;n[i]++}}END{for(i=1;i<=80;i++)printf "%.6f ",s[i]/n[i]}' /tmp/em_all.fr)
# supervector: raw (no cmvn) or cmvn (subtract global mean), pool mean+std -> 160-d
sv(){ awk -v gm="$GM" -v c="$2" 'BEGIN{split(gm,g," ")}
  {for(i=1;i<=NF;i++){v=$i; if(c=="1")v=$i-g[i]; s[i]+=v;q[i]+=v*v;n[i]++}}
  END{for(i=1;i<=80;i++){m=s[i]/n[i];printf "%.5f ",m} for(i=1;i<=80;i++){m=s[i]/n[i];vv=q[i]/n[i]-m*m;if(vv<0)vv=0;printf "%.5f ",sqrt(vv)}}' "/tmp/em_$1.fr"; }
cos(){ paste -d' ' <(echo "$1") <(echo "$2")|awk '{n=NF/2;d=0;a=0;b=0;for(i=1;i<=n;i++){d+=$i*$(i+n);a+=$i*$i;b+=$(i+n)*$(i+n)}printf "%.5f",d/(sqrt(a)*sqrt(b)+1e-9)}'; }
label(){ # genuine(1) if same speaker pair (0,1)(2,3)(4,5)
  case "$1-$2" in 0-1|2-3|4-5) echo 1.0;; *) echo 0.0;; esac; }
build_trials(){ local cmvn="$1" tr="" sv_=(); local i
  for i in 0 1 2 3 4 5; do sv_[$i]=$(sv $i $cmvn); done
  for i in 0 1 2 3 4 5; do for ((j=i+1;j<6;j++)); do
    tr="$tr (list $(cos "${sv_[i]}" "${sv_[j]}") $(label $i $j))"; done; done
  echo "$tr"; }
run_eer(){ echo "(do (print (eer (list $1))))" > /tmp/em_eer.fk
  $K form-stdlib/transformer-numerics.fk form-stdlib/eer.fk /tmp/em_eer.fk 2>/dev/null | grep -E '^-?[0-9]' | tail -1; }
echo; echo "15 trials (3 genuine same-speaker, 12 impostor cross-speaker). EER via eer.fk:"
echo "  log-mel RAW   EER = $(run_eer "$(build_trials 0)")"
echo "  log-mel+CMVN  EER = $(run_eer "$(build_trials 1)")   (0=perfect separation, 0.5=chance)"
rm -f /tmp/em_*.fr /tmp/em_col.fk /tmp/em_eer.fk
