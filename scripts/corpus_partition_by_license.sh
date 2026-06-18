#!/usr/bin/env bash
# corpus_partition_by_license.sh — split a downloaded corpus into the part that is
# LAWFUL TO TRAIN ON and the part that is TEST-ONLY, enforcing "we cannot train on
# copyrighted material" as a hard gate.
#
# The DECISION lives in Form: form-stdlib/corpus-license-gate.fk's clg-phase routes
# a provenance tag to "train" | "eval", FAIL-CLOSED (only an allowlisted lawful tag
# trains; copyright and UNKNOWN/absent provenance route to eval-only). This script
# is a thin host-IO carrier — it reads rows, asks the Form gate to classify the
# DISTINCT provenance tags (one kernel call), and writes two files. The legal
# boundary is decided by the four-way-proven recipe (corpus-license-gate-band 31),
# not by this carrier.
#
# Each corpus row (JSONL) may carry "license" or "provenance". Untagged rows take
# --default-license (the operator's explicit provenance assertion); with no default
# they are treated as "unknown" and routed to eval-only — never silently trained on.
# A row tagged copyright/all-rights-reserved is forced to eval-only regardless of
# the default.
#
# Usage:
#   corpus_partition_by_license.sh <corpus.jsonl> [--default-license <tag>] [--out-dir <dir>]
# Example (the body's own captured oracle turns are "owned" work product):
#   corpus_partition_by_license.sh ~/.coherence-network/form-cli-corpus/corpus.jsonl \
#       --default-license owned
# Emits, beside the corpus: <stem>.train-eligible.jsonl  and  <stem>.eval-only.jsonl
#
# Companion: docs/coherence-substrate/offline-nl-translation-training.form
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"

CORPUS="${1:-}"; shift || true
DEFAULT_LICENSE="unknown"; OUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --default-license) DEFAULT_LICENSE="$2"; shift 2 ;;
    --out-dir)         OUT_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
done
[[ -n "$CORPUS" && -f "$CORPUS" ]] || { echo "usage: corpus_partition_by_license.sh <corpus.jsonl> [--default-license tag] [--out-dir dir]"; exit 1; }
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && GOPROXY=off go build -o bin-go . ) 2>/dev/null  # offline: build from module cache, never the network
[[ -n "$OUT_DIR" ]] || OUT_DIR="$(dirname "$CORPUS")"
stem="$(basename "${CORPUS%.jsonl}")"
TRAIN_OUT="$OUT_DIR/$stem.train-eligible.jsonl"
EVAL_OUT="$OUT_DIR/$stem.eval-only.jsonl"

# 1) collect the DISTINCT provenance tags present in the corpus (carrier IO).
tags="$(python3 - "$CORPUS" "$DEFAULT_LICENSE" <<'PY'
import json,sys
path,default=sys.argv[1],sys.argv[2]
seen=[]
for l in open(path):
    try: r=json.loads(l)
    except: continue
    t=str(r.get("license") or r.get("provenance") or default).strip().lower() or "unknown"
    if t not in seen: seen.append(t)
print("\n".join(seen))
PY
)"
[[ -n "$tags" ]] || { echo "no rows in $CORPUS"; exit 1; }

# 2) ask the Form gate to classify each distinct tag (the DECISION, four-way recipe).
prog="$(mktemp)"
{ cat "$STD/corpus-license-gate.fk"
  echo "(do"
  while IFS= read -r t; do echo "  (print (clg-phase \"$t\"))"; done <<<"$tags"
  echo "  0)"
} > "$prog"
phases="$("$GO" "$prog" 2>/dev/null | grep -E '^(train|eval)$')"
rm -f "$prog"
[[ -n "$phases" ]] || { echo "Form gate produced no classification — is bin-go built?"; exit 1; }

# 3) partition rows by the Form gate's decision (carrier IO). Fail-closed: a tag the
#    gate did not classify, or any error, routes the row to eval-only.
python3 - "$CORPUS" "$DEFAULT_LICENSE" "$TRAIN_OUT" "$EVAL_OUT" <<PY
import json,sys
path,default,train_out,eval_out=sys.argv[1:5]
tags="""$tags""".strip().split("\n")
phases="""$phases""".strip().split("\n")
phase_of=dict(zip(tags,phases))
ntr=nev=0; bad=0
with open(train_out,"w") as ft, open(eval_out,"w") as fe:
    for l in open(path):
        try: r=json.loads(l)
        except: continue
        t=str(r.get("license") or r.get("provenance") or default).strip().lower() or "unknown"
        ph=phase_of.get(t,"eval")  # fail-closed default
        if ph=="train": ft.write(l if l.endswith("\n") else l+"\n"); ntr+=1
        else:           fe.write(l if l.endswith("\n") else l+"\n"); nev+=1
        if t in ("copyright","all-rights-reserved","copyrighted") and ph!="eval": bad+=1
sys.stderr.write("partitioned: %d train-eligible, %d eval-only\n"%(ntr,nev))
if bad: sys.stderr.write("GATE VIOLATION: %d copyright rows leaked into train — aborting\n"%bad); sys.exit(3)
PY
rc=$?
[[ $rc -eq 0 ]] || { echo "partition failed (rc=$rc)"; exit $rc; }

echo
echo "── corpus partitioned by the four-way Form license gate ──"
printf "  train-eligible    %s\n" "$TRAIN_OUT"
printf "  eval-only (test)  %s\n" "$EVAL_OUT"
echo "  classification (Form clg-phase, fail-closed):"
paste <(echo "$tags") <(echo "$phases") | while IFS=$'\t' read -r t p; do printf "    %-20s → %s\n" "$t" "$p"; done
echo
echo "  → train the model on the train-eligible file ONLY; measure on the eval-only (copyright) file."
echo "    form_cli_transformer_train_wide.sh $TRAIN_OUT 60 200 $EVAL_OUT"
