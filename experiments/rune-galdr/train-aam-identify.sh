#!/usr/bin/env bash
# train-aam-identify.sh — the first END-TO-END real-data test: does a TRAINED AAM head beat untrained
# features at recognizing the ceremony speakers?
#
# 3 voices × 6 log-mel mean supervectors (mean-only — std is nuisance, per the EER decomposition); 4 train
# + 2 held per speaker. Closed-set identification (argmax_j cosθ_j over the AAM class columns):
#   - UNTRAINED baseline: nearest train-CENTROID.
#   - TRAINED: aat-train (the four-way AAM trainer) from an ambiguous identical init.
# Both classify the 6 held-out segments; we report accuracy vs chance (1/3). The trainer + classifier are
# the Form body (speaker-aam-train); this carrier only assembles supervectors and reads the verdict.
# Recordings/roster stay private; only the accuracy leaves.
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
spk=(ubbe brigitte angelia); offs=(1.0 3.0 5.0 7.0 9.0 11.0)   # 6 crops/speaker: [0..3]=train, [4,5]=held
mean(){ awk '{for(i=1;i<=NF;i++){s[i]+=$i;n[i]++}}END{for(i=1;i<=80;i++)printf "%.5f ",s[i]/n[i]}' "$1"; }
echo "extracting log-mel mean supervectors: 3 voices × 6 crops × 4 frames (~58s)..."
declare -a SV   # SV[spk*6+crop] = 80-d mean supervector
for s in 0 1 2; do for c in 0 1 2 3 4 5; do : > /tmp/ti.fr
  for d in 0.0 0.4 0.8 1.2; do t=$(awk "BEGIN{print ${offs[c]}+$d}")
    col "$SEP/${spk[s]}.16k/vocals.wav" "$t" > /tmp/ti_col.fk
    $K $PRE /tmp/ti_col.fk 2>/dev/null | grep -E '^\[' | tr -d '[]' | tr ',' ' ' >> /tmp/ti.fr; done
  SV[$((s*6+c))]=$(mean /tmp/ti.fr); done; done
flist(){ printf '(list %s)' "$1"; }
# centroid per speaker = mean of its 4 train supervectors
centroid(){ local s=$1; printf '%s\n%s\n%s\n%s\n' "${SV[$((s*6+0))]}" "${SV[$((s*6+1))]}" "${SV[$((s*6+2))]}" "${SV[$((s*6+3))]}" \
  | awk '{for(i=1;i<=NF;i++){a[i]+=$i;n[i]++}}END{for(i=1;i<=80;i++)printf "%.5f ",a[i]/n[i]}'; }
# build the Form program: train corpus (12), centroid W (3), held set (6) → print trained preds + centroid preds
{
  printf '(do\n'
  printf '  (let neutral (list %s %s %s))\n' "$(flist "$(yes 0.1 | head -80 | tr '\n' ' ')")" "$(flist "$(yes 0.1 | head -80 | tr '\n' ' ')")" "$(flist "$(yes 0.1 | head -80 | tr '\n' ' ')")"
  printf '  (let corpus (list'
  for s in 0 1 2; do for c in 0 1 2 3; do printf ' (list %s %d)' "$(flist "${SV[$((s*6+c))]}")" "$s"; done; done
  printf '))\n'
  printf '  (let Wt (aat-train neutral corpus 6.0 0.995 0.0998 0.02 120))\n'
  printf '  (let Wc (list %s %s %s))\n' "$(flist "$(centroid 0)")" "$(flist "$(centroid 1)")" "$(flist "$(centroid 2)")"
  printf '  (print (list'; for s in 0 1 2; do for c in 4 5; do printf ' (aat-classify Wt %s)' "$(flist "${SV[$((s*6+c))]}")"; done; done; printf '))\n'
  printf '  (print (list'; for s in 0 1 2; do for c in 4 5; do printf ' (aat-classify Wc %s)' "$(flist "${SV[$((s*6+c))]}")"; done; done; printf '))\n'
  printf '  (print (list'; for s in 0 1 2; do for c in 0 1 2 3; do printf ' (aat-classify Wt %s)' "$(flist "${SV[$((s*6+c))]}")"; done; done; printf ')))\n'
} > /tmp/ti_prog.fk
echo "training (AAM, 60 epochs) + classifying 6 held-out..."
out=$($K form-stdlib/transformer-numerics.fk form-stdlib/loss.fk form-stdlib/speaker-aam.fk form-stdlib/speaker-aam-train.fk /tmp/ti_prog.fk 2>/dev/null | grep -E '^\[')
trained=$(echo "$out" | sed -n '1p' | tr -d '[]' | tr ',' ' ')
centro=$( echo "$out" | sed -n '2p' | tr -d '[]' | tr ',' ' ')
traincl=$(echo "$out" | sed -n '3p' | tr -d '[]' | tr ',' ' ')
truth="0 0 1 1 2 2"; truth_tr="0 0 0 0 1 1 1 1 2 2 2 2"
acc(){ awk -v p="$1" -v t="$2" 'BEGIN{np=split(p,P," ");split(t,T," ");c=0;for(i=1;i<=np;i++)if(P[i]==T[i])c++;printf "%d/%d = %.0f%%",c,np,100*c/np}'; }
echo
echo "held-out identification (6 segments, 3 speakers; chance = 33%):"
echo "  preds (truth $truth)"
echo "  untrained nearest-centroid : $centro  → $(acc "$centro" "$truth")"
echo "  TRAINED AAM head           : $trained  → $(acc "$trained" "$truth")"
echo "  [diagnostic] TRAIN-set acc : $traincl  → $(acc "$traincl" "$truth_tr")  (100% train + low held = overfit)"
rm -f /tmp/ti.fr /tmp/ti_col.fk /tmp/ti_prog.fk
