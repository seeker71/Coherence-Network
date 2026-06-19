#!/usr/bin/env bash
# form_cli_neural_lm_train.sh — train the Form-native neural LM (neural-lm.fk) on the
# REAL lawful corpus, offline, and measure it against a baseline on held-out text.
#
# This is the NON-TOY proof: real words from our own captured oracle turns (owned,
# train-eligible), real distributional embeddings, real bigram next-word prediction,
# a real train/held split. The LOGIC is four-way Form — tct-train folds the proven
# residual stack (transformer-corpus-train 31), nl-render snaps to the nearest token
# (neural-lm 31), nl-eval-correct counts held-out hits. This script is a thin host-IO
# carrier: it tokenizes the corpus, builds the vocabulary + co-occurrence embeddings
# + bigram pairs, emits the Form program, and reports model vs unigram-baseline
# held-out accuracy plus a live generated word sample.
#
# Offline: all compute via the local Go kernel binary over a file already on disk;
# no network. Companion: docs/coherence-substrate/offline-nl-translation-training.form
# Usage: form_cli_neural_lm_train.sh [corpus] [vocab=24] [dim=8] [epochs=300] [cap=600] [emb=onehot|dist]
# emb=onehot (default): each word is its own axis (dim forced to vocab) — the block learns
#   each context's empirical successor distribution, argmax = modal next word (a real bigram LM).
# emb=dist: distributional co-occurrence embeddings — generalisation-capable, but mean-regresses
#   on multi-modal successors; kept for comparison.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
# deterministic walk: the bespoke Go float JIT is not bit-identical (see
# docs/coherence-substrate/one-acceleration-engine.form); FORM_JIT_HOT forces the
# walk so the reported accuracy is reproducible until the unified pipeline lands.
export FORM_JIT_HOT=100000000
CORPUS="${1:-${FORM_CLI_CORPUS:-$HOME/.coherence-network/form-cli-corpus/corpus.jsonl}}"
VOCAB="${2:-24}"; DIM="${3:-8}"; EPOCHS="${4:-300}"; CAP="${5:-600}"; EMB="${6:-onehot}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && GOPROXY=off go build -o bin-go . ) 2>/dev/null
[[ -f "$CORPUS" ]] || { echo "no corpus at $CORPUS"; exit 1; }

echo "── train the Form-native neural LM on the REAL lawful corpus (logic is four-way Form) ──"

# Featurize the real corpus (carrier IO): tokenize → vocab → distributional embeddings
# → bigram pairs → train/held split → emit the Form program body + report fields.
WORK="$(mktemp -d)"
python3 - "$CORPUS" "$VOCAB" "$DIM" "$CAP" "$WORK" "$EMB" <<'PY'
import json,sys,re,math
path,V,D,CAP,work,mode=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),sys.argv[5],sys.argv[6]
TOK=re.compile(r"[a-z]{3,}")
# stream the corpus into a flat token list (task + reasoning text — our own turns).
toks=[]
for l in open(path):
    try: r=json.loads(l)
    except: continue
    text=(str(r.get("task",""))+" "+str(r.get("reasoning",""))).lower()
    toks.extend(TOK.findall(text))
from collections import Counter
freq=Counter(toks)
vocab=[w for w,_ in freq.most_common(V)]
idx={w:i for i,w in enumerate(vocab)}
anchors=vocab[:D]                       # the D most frequent words are the embedding axes
aidx={w:j for j,w in enumerate(anchors)}
# distributional embedding: forward+backward co-occurrence (adjacent) over the D anchors,
# L1-normalized — words used in similar neighbourhoods get similar vectors (real semantics).
co=[[0.0]*D for _ in range(len(vocab))]
for a,b in zip(toks,toks[1:]):
    if a in idx and b in aidx: co[idx[a]][aidx[b]]+=1.0
    if b in idx and a in aidx: co[idx[b]][aidx[a]]+=1.0
if mode=="onehot":
    D=len(vocab)                        # each word is its own axis
    emb=[[1.0 if j==i else 0.0 for j in range(D)] for i in range(len(vocab))]
else:
    emb=[]
    for row in co:
        s=sum(row)
        emb.append([ (x/s if s>0 else 0.0) for x in row ] if s>0 else [1.0/D]*D)
# bigram (context, next) pairs over in-vocab adjacent tokens.
pairs=[(idx[a],idx[b]) for a,b in zip(toks,toks[1:]) if a in idx and b in idx][:CAP]
n=len(pairs); ntr=int(n*0.8)
train=pairs[:ntr]; held=pairs[ntr:]
def vec(v): return "(list "+" ".join("%.6f"%x for x in v)+")"
def emit_E(): return "(let E (list "+" ".join(vec(e) for e in emb)+"))"
def emit_train(): return "(let train (list "+" ".join("(list %s %s)"%(vec(emb[a]),vec(emb[b])) for a,b in train)+"))"
def emit_held():  return "(let held (list "+" ".join("(list %s %d)"%(vec(emb[a]),b) for a,b in held)+"))"
# deterministic small init matrices (DxD), biases 0 — no RNG (kernel forbids it).
def mat():
    rows=[]
    for i in range(D):
        rows.append("(list "+" ".join("%.4f"%(0.2*math.sin(i*2.0+j*0.7+1.0)) for j in range(D))+")")
    return "(list "+" ".join(rows)+")"
def zeros(): return "(list "+" ".join("0.0" for _ in range(D))+")"
def block(): return "(tbp-bk %s %s %s %s)"%(mat(),zeros(),mat(),zeros())
open(work+"/body.fk","w").write("\n".join([emit_E(),emit_train(),emit_held(),
    "(let ba %s)"%block(),"(let bb %s)"%block()]))
# baseline: most-frequent vocab word; its held-out accuracy (carrier arithmetic, not logic).
base_i=0; base_hits=sum(1 for _,b in held if b==base_i)
open(work+"/meta.txt","w").write("%d %d %d %d %s %d %s\n"%(
    len(vocab),D,len(train),len(held),vocab[base_i],base_hits," ".join(vocab)))
# seed for generation = the most frequent CONTENT word (skip the top function word).
open(work+"/seed.txt","w").write(str(min(1,len(vocab)-1)))
sys.stderr.write("vocab=%d dim=%d train=%d held=%d (real corpus bigrams)\n"%(len(vocab),D,len(train),len(held)))
PY
[[ -s "$WORK/body.fk" ]] || { echo "featurization produced nothing"; rm -rf "$WORK"; exit 1; }
read -r NVOC NDIM NTR NHD BASEW BASEHITS REST < "$WORK/meta.txt"; VOCWORDS="$BASEW $REST"
SEED="$(cat "$WORK/seed.txt")"

prog="$WORK/prog.fk"
{ cat "$STD/transformer-numerics.fk" "$STD/transformer-block.fk" "$STD/transformer-backprop.fk" "$STD/transformer-corpus-train.fk" "$STD/neural-lm.fk"
  echo "(do"
  cat "$WORK/body.fk"
  echo "  (let eps 0.00001) (let lr 0.05)"
  echo "  (let s0 (list ba bb))"
  echo "  (let sN (tct-train-blocks ba bb train lr eps $EPOCHS))"
  echo "  (print (nl-eval-correct sN E held eps))"         # line 1: model held-out hits
  echo "  (print (len held))"                              # line 2
  # line 3..: a 12-token generation from the seed word
  echo "  (let g (nl-gen sN E (nl-emb E $SEED) 12 eps))"
  for k in 0 1 2 3 4 5 6 7 8 9 10 11; do echo "  (print (nth g $k))"; done
  echo "  0)"
} > "$prog"
out="$("$GO" "$prog" 2>/dev/null | grep -E '^-?[0-9]+$')"
hits=$(sed -n '1p' <<<"$out"); nh=$(sed -n '2p' <<<"$out")
gen_idx=$(sed -n '3,14p' <<<"$out" | tr '\n' ' ')
rm -rf "$WORK"

# map generated indices → words
read -r -a VW <<< "$VOCWORDS"
gen_words=""; for i in $gen_idx; do gen_words+="${VW[$i]} "; done

pct(){ awk -v a="$1" -v b="$2" 'BEGIN{ if(b>0) printf "%.1f%%", 100.0*a/b; else printf "n/a" }'; }
echo
printf "  corpus            %s real bigram pairs (%s train, %s held) from our own lawful turns\n" "$((NTR+NHD))" "$NTR" "$NHD"
printf "  vocabulary        %s real words, %s-dim %s embeddings\n" "$NVOC" "$NDIM" "$EMB"
printf "  model held-out    %s / %s correct next-word = %s\n" "$hits" "$nh" "$(pct "$hits" "$nh")"
printf "  unigram baseline  %s / %s (always predict \"%s\") = %s\n" "$BASEHITS" "$NHD" "$BASEW" "$(pct "$BASEHITS" "$NHD")"
printf "  generated (seed \"%s\"): %s\n" "${VW[$SEED]}" "$gen_words"
awk -v m="$hits" -v b="$BASEHITS" 'BEGIN{ if(m>b) print "  → the Form-native neural LM beats the unigram baseline on held-out real text, offline." }'