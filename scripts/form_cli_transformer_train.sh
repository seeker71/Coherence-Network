#!/usr/bin/env bash
# form_cli_transformer_train.sh — train the Form-native transformer on the REAL
# captured oracle corpus.
#
# The LOGIC is Form: transformer-corpus-train.fk folds the proven two-block
# residual SGD atom over a corpus, four-way proven (Go/Rust/TS/fkwu) by
# tests/transformer-corpus-train-band.fk. This is a thin host-IO carrier: it reads
# the body's 949-turn corpus of the trusted remote oracle's (Claude's) turns,
# featurizes each into a (x, t) row — x = [task-length, code-word-present],
# t = [Read-used, Edit-used] (the oracle's REAL tool behavior) — splits train/held
# (every 5th held), emits a Form program that trains the native transformer through
# the proven recipe, and reports train + held-out loss falling on real data.
#
# Width is the proven floor (2→2→2); the recipe is dimension-generic, so widening
# is data+capacity, not new logic. Usage: form_cli_transformer_train.sh [corpus] [epochs] [cap]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
CORPUS="${1:-${FORM_CLI_CORPUS:-$HOME/.coherence-network/form-cli-corpus/corpus.jsonl}}"
EPOCHS="${2:-30}"; CAP="${3:-200}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null
[[ -f "$CORPUS" ]] || { echo "no corpus at $CORPUS"; exit 1; }

echo "── train the Form-native transformer on the real oracle corpus (logic is four-way Form) ──"

# featurize the corpus into Form (x t) rows; split train/held; emit the program body
body="$(python3 - "$CORPUS" "$CAP" <<'PY'
import json,sys,re
path,cap=sys.argv[1],int(sys.argv[2])
KW=re.compile(r"\b(file|code|fix|bug|function|test|error|class|import|build|deploy|kernel)\b", re.I)
def feat(t):
    task=str(t.get("task",""))
    xlen=min(len(task)/300.0,1.0)
    xkw=1.0 if KW.search(task) else 0.0
    tools=set(st.get("tool") for st in t.get("steps",[]) if isinstance(st,dict))
    return (round(xlen,4), xkw, 1.0 if "Read" in tools else 0.0, 1.0 if "Edit" in tools else 0.0)
rows=[]
for l in open(path):
    try: r=json.loads(l)
    except: continue
    if not r.get("steps"): continue
    rows.append(feat(r))
train=[r for i,r in enumerate(rows) if i%5!=0][:cap]
held =[r for i,r in enumerate(rows) if i%5==0][:max(1,cap//4)]
def flist(rs): return "(list "+" ".join("(list (list %s %s) (list %s %s))"%(a,b,c,d) for (a,b,c,d) in rs)+")"
print("(let train %s)"%flist(train))
print("(let held %s)"%flist(held))
sys.stderr.write("featurized: %d train, %d held (real corpus turns)\n"%(len(train),len(held)))
PY
)"
[[ -n "$body" ]] || { echo "featurization produced no rows"; exit 1; }

prog="$(mktemp)"
{ cat "$STD/transformer-numerics.fk" "$STD/transformer-block.fk" "$STD/transformer-backprop.fk" "$STD/transformer-corpus-train.fk"
  echo "(do"
  # untrained block inits (small, the proven-shape init)
  echo "  (let ba (tbp-bk (list (list 0.3 -0.2) (list 0.1 0.4)) (list 0.0 0.0) (list (list 0.5 0.2) (list -0.3 0.6)) (list 0.0 0.0)))"
  echo "  (let bb (tbp-bk (list (list 0.2 0.1) (list -0.1 0.3)) (list 0.0 0.0) (list (list 0.4 -0.2) (list 0.3 0.5)) (list 0.0 0.0)))"
  echo "  $body"
  echo "  (let eps 0.00001) (let lr 0.05)"
  echo "  (let s0 (list ba bb))"
  echo "  (let sN (tct-train-blocks ba bb train lr eps $EPOCHS))"
  echo "  (print (round (mul (tct-corpus-loss s0 train eps) 1000000.0)))"
  echo "  (print (round (mul (tct-corpus-loss sN train eps) 1000000.0)))"
  echo "  (print (round (mul (tct-corpus-loss s0 held eps) 1000000.0)))"
  echo "  (print (round (mul (tct-corpus-loss sN held eps) 1000000.0)))"
  echo "  (print (len train)) (print (len held)) 0)"
} > "$prog"
out="$("$GO" "$prog" 2>/dev/null | grep -E '^-?[0-9]+$')"; rm -f "$prog"
tr0=$(sed -n '1p' <<<"$out"); trN=$(sed -n '2p' <<<"$out")
hd0=$(sed -n '3p' <<<"$out"); hdN=$(sed -n '4p' <<<"$out")
ntr=$(sed -n '5p' <<<"$out"); nhd=$(sed -n '6p' <<<"$out")
f6(){ printf "%d.%06d" "$(( ${1:-0}/1000000 ))" "$(( ${1:-0}<0 ? -${1:-0}%1000000 : ${1:-0}%1000000 ))"; }

echo
printf "  corpus            %s train turns, %s held-out (real Claude turns)\n" "$ntr" "$nhd"
printf "  epochs            %s   (SGD lr=0.05, two-block residual stack)\n" "$EPOCHS"
printf "  train loss        %s  →  %s\n" "$(f6 "$tr0")" "$(f6 "$trN")"
printf "  held-out loss     %s  →  %s\n" "$(f6 "$hd0")" "$(f6 "$hdN")"
if [[ "${trN:-1}" -lt "${tr0:-0}" && "${hdN:-1}" -lt "${hd0:-0}" ]]; then
  echo "  → the Form-native transformer learned the oracle's real tool behavior and generalized to held-out turns."
fi
