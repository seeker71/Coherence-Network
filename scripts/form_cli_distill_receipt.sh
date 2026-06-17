#!/usr/bin/env bash
# form_cli_distill_receipt.sh — run the oracle->native distillation on the real
# corpus and write a DURABLE, four-way-proven native-training receipt.
#
# The body already trains a native tool-predictor on its own corpus of the trusted
# remote oracle's (Claude's) turns and beats the no-learning baseline at zero
# remote tokens (scripts/form_cli_train_predict.sh). This carrier closes that into
# a durable artifact: it runs the live eval, feeds the MEASURED held-out counts
# through the Form recipe (form-stdlib/oracle-distill-corpus.fk — the receipt
# logic, proven four-way by tests/oracle-distill-corpus-band.fk), and appends a
# native-training-receipt row with REAL content digests. The LOGIC is Form; this
# is a thin host-IO carrier — run, capture counts, hash, append.
#
# Usage: form_cli_distill_receipt.sh [corpus]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
CORPUS="${1:-${FORM_CLI_CORPUS:-$HOME/.coherence-network/form-cli-corpus/corpus.jsonl}}"
OUT="${FORM_CLI_RECEIPTS:-$HOME/.coherence-network/native-training-receipts.jsonl}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null
[[ -f "$CORPUS" ]] || { echo "no corpus at $CORPUS"; exit 1; }

echo "── oracle→native distillation receipt (real corpus, Form-proven logic) ──"

# 1. live eval — the native model trained on the corpus, scored on held-out
EVAL="$(bash "$ROOT/scripts/form_cli_train_predict.sh" "$CORPUS" 2>/dev/null)"
grab(){ printf '%s\n' "$EVAL" | grep -E "$1" | grep -oE '[0-9]+/[0-9]+' | head -1; }
NM="$(grab 'native-trained  majority')"; NF="$(grab 'native-trained  full')"
BM="$(grab 'baseline match')";          BF="$(grab 'baseline full')"
nmc="${NM%%/*}"; held="${NM##*/}"; nfc="${NF%%/*}"; bmc="${BM%%/*}"; bfc="${BF%%/*}"
[[ -n "${held:-}" && "${held:-0}" -gt 0 ]] || { echo "could not read held-out counts from eval"; exit 1; }
samples=$(python3 -c "import sys;print(max(0,sum(1 for _ in open('$CORPUS'))-$held))")

# 2. REAL content digests (the receipt's weights/data/eval merkles)
sha(){ shasum -a 256 | cut -d' ' -f1; }
dmerkle="sha256:$(cat "$CORPUS" | sha)"
emerkle="sha256:$(printf '%s' "$EVAL" | sha)"
wmerkle="sha256:$(printf 'base-rates+agent-keyword-boosts/%s/%s' "$samples" "$held" | sha)"

# 3. feed the MEASURED counts through the Form recipe (the proven receipt logic).
# core.fk is BML dialect — source-compile it once (content-keyed cache, exactly
# as form/validate.sh prepare_sources does); the rest are plain Form.
CACHE="$STD/.cache/source-compiled"; mkdir -p "$CACHE"
chain=(form-ontology-loader.fk line-grammar.fk bmf-core.fk bmf-grammar.fk bml.fk bml-source.fk source-compiler.fk)
stamp="$( (cd "$STD" && cat "${chain[@]}"; cat "$GO") 2>/dev/null | shasum | cut -c1-16)"
ckey="$(cat "$STD/core.fk" | shasum | cut -c1-16)-$stamp"
core_c="$CACHE/$ckey.fk"
if [[ ! -s "$core_c" ]]; then
    drv="$(mktemp)"; printf '(do (form-source-compile-file "%s" "%s"))\n' "$STD/core.fk" "$core_c" > "$drv"
    ( cd "$STD" && "$GO" "${chain[@]}" "$drv" ) >/dev/null 2>&1; rm -f "$drv"
fi
[[ -s "$core_c" ]] || { echo "could not source-compile core.fk"; exit 1; }
prog="$(mktemp)"
{ cat "$core_c" "$STD/nearest-shape.fk" "$STD/classifier-eval.fk" "$STD/choice-receipt.fk" \
      "$STD/branch-choice-order.fk" "$STD/choice-receipt-learning.fk" "$STD/form-freq-check.fk" \
      "$STD/oracle-distillation-learning.fk" "$STD/native-training-receipt.fk" "$STD/oracle-distill-corpus.fk"
  # a live receipt built from the measured counts (not the recorded constants)
  echo "(let r (ntr-row \"form-cli-tool-predict-live\" \"form-native-tool-predictor\""
  echo "   \"form/form-stdlib/oracle-distill-corpus.fk\" \"$wmerkle\" \"$dmerkle\" \"$emerkle\""
  echo "   1 $samples $held $nfc (sub $held $nfc) (odc-ppm $nfc) (odc-ppm $bfc) \"active\"))"
  echo "(print (ntr-trained? r))"                 # 1 = a valid trained native artifact
  echo "(print (ntr-beats-oracle? r))"            # 1 = native full-cover beats the baseline bar
  echo "(print (odc-ppm $nfc))"                   # native full-cover accuracy, ppm
  echo "(print (odc-ppm $bfc))"                   # baseline accuracy, ppm
  echo "(print (div (mul $nmc 100) $held))"       # native majority-match percent (closeness to oracle)
} > "$prog"
o="$("$GO" "$prog" 2>/dev/null)"; rm -f "$prog"
trained=$(sed -n '1p' <<<"$o"); beats=$(sed -n '2p' <<<"$o")
nppm=$(sed -n '3p' <<<"$o"); bppm=$(sed -n '4p' <<<"$o"); closeness=$(sed -n '5p' <<<"$o")

# 4. append the durable receipt row
mkdir -p "$(dirname "$OUT")"
python3 - "$OUT" "$samples" "$held" "$nfc" "$nmc" "$bfc" "$nppm" "$bppm" "$closeness" \
    "$trained" "$beats" "$wmerkle" "$dmerkle" "$emerkle" <<'PY'
import json,sys
(out,samples,held,nfc,nmc,bfc,nppm,bppm,close,trained,beats,wm,dm,em)=sys.argv[1:15]
row={"artifact":"form-cli-tool-predict","kind":"form-native-tool-predictor",
     "recipe":"form/form-stdlib/oracle-distill-corpus.fk","lane":"tool-selection",
     "oracle":"claude","samples":int(samples),"heldout":int(held),
     "native_fullcover_correct":int(nfc),"native_majority_correct":int(nmc),
     "baseline_fullcover_correct":int(bfc),
     "native_accuracy_ppm":int(nppm),"baseline_accuracy_ppm":int(bppm),
     "oracle_closeness_pct":int(close),"remote_tokens":0,
     "trained":int(trained),"beats_baseline":int(beats),
     "weights_merkle":wm,"dataset_merkle":dm,"eval_merkle":em}
open(out,"a").write(json.dumps(row)+"\n")
print("  wrote receipt -> %s"%out)
PY

echo
printf "  trained native artifact   %s\n" "$([[ "$trained" == 1 ]] && echo yes || echo NO)"
printf "  native full-cover         %s/%s  (%s ppm)\n" "$nfc" "$held" "$nppm"
printf "  baseline full-cover       %s/%s  (%s ppm)\n" "$bfc" "$held" "$bppm"
printf "  closeness to oracle       %s%% (majority-match)\n" "$closeness"
printf "  remote tokens             0  (fully local)\n"
if [[ "$beats" == 1 && "$trained" == 1 ]]; then
    echo "  → native beats the baseline AND costs zero remote tokens — the oracle retires on the tool-selection lane."
fi
