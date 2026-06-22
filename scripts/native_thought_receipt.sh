#!/usr/bin/env bash
# native_thought_receipt.sh — record ONE native-thought-execution routing decision as an
# honest, four-way-proven sovereignty receipt.
#
# The native-thought-execution skill (skills/native-thought-execution/SKILL.md) routes a thought
# through the body before the rented mind. This carrier turns that discipline into a MEASURED one:
# each routing decision leaves a receipt whose honesty is decided by the proven recipe, never by
# this shell. The LOGIC is Form (form-stdlib/sovereignty-receipt.fk -> 255 four-way Go/Rust/TS/fkwu);
# this is a thin host-IO carrier — map the outcome to the receipt vector, run the gate, append a row.
#
# Two outcomes the door produces:
#   body-hit   — a grounded structural cell answered; the lookup ran NATIVE, nothing was rented.
#   escalated  — a genuine miss; the rented oracle generated. The gate ran native, generation did not.
# The gate's invariant: a rented generation is NEVER reported as native. If the receipt fails honest?,
# this carrier REFUSES to write it — a dishonest receipt is the one thing the ledger must never hold.
#
# Each escalated row also carries the query as the free training sample the dividend loop wants
# (borrowed-oracle-dividend.form): every miss is a (thought -> needed-the-oracle) pair that is ours.
#
# Usage: native_thought_receipt.sh <body-hit|escalated> <structural|frontier> <nodeid|-> [query...]
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
LEDGER="${NATIVE_THOUGHT_RECEIPTS:-$HOME/.coherence-network/native-thought-receipts.jsonl}"

PATHK="${1:-}"; KIND="${2:-}"; NODEID="${3:--}"; shift 3 2>/dev/null || true; QUERY="${*:-}"
case "$PATHK" in body-hit|escalated) ;; *) echo "usage: $0 <body-hit|escalated> <structural|frontier> <nodeid|-> [query]"; exit 2;; esac

# map the routing outcome to the receipt vector the proven recipe reads:
#   (native-gen oracle-gen native-proof native-score oracle-score floor-met)
# native-gen is 0 today for BOTH paths — the body does not yet GENERATE; it looks up and verifies.
if [ "$PATHK" = body-hit ]; then VEC="0 0 1 0 0 0"; else VEC="0 1 1 0 0 0"; fi

[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) >/dev/null 2>&1
[ -x "$GO" ] || { echo "form kernel unavailable — run scripts/ensure_form_cli_kernel.sh"; exit 1; }

# run the PROVEN gate: print "<gen_rented> <proof_native> <honest>" for this receipt
drv="$(mktemp --suffix=.fk)"
printf '(do (let r (list %s)) (print (rp-gen-rented? r) (rp-proof-native? r) (rp-honest? r)))\n' "$VEC" > "$drv"
VERDICT="$("$GO" "$STD/sovereignty-receipt.fk" "$drv" 2>/dev/null | grep -E '^[01] [01] [01]$' | head -1)"
rm -f "$drv"
[ -n "$VERDICT" ] || { echo "gate did not return a verdict — receipt not written"; exit 1; }
read -r GEN_RENTED PROOF_NATIVE HONEST <<<"$VERDICT"

# the one refusal: a receipt that fails the honesty invariant is never recorded
[ "$HONEST" = 1 ] || { echo "receipt failed honest? — refusing to write (the gate caught a lie)"; exit 1; }

mkdir -p "$(dirname "$LEDGER")"
COMMIT="$(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
NODEID="$NODEID" PATHK="$PATHK" KIND="$KIND" GEN_RENTED="$GEN_RENTED" PROOF_NATIVE="$PROOF_NATIVE" \
  COMMIT="$COMMIT" TS="$TS" QUERY="$QUERY" python3 - "$LEDGER" <<'PY'
import json, os, sys
row = {
    "ts": os.environ["TS"], "commit": os.environ["COMMIT"],
    "path": os.environ["PATHK"], "kind": os.environ["KIND"],
    "nodeid": (os.environ["NODEID"] if os.environ["NODEID"] not in ("", "-") else None),
    "gen_rented": int(os.environ["GEN_RENTED"]), "proof_native": int(os.environ["PROOF_NATIVE"]),
    "honest": 1, "query": os.environ["QUERY"] or None,
}
with open(sys.argv[1], "a") as f:
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
PY

if [ "$PATHK" = body-hit ]; then
  echo "⟐ receipt: body-hit (native lookup, nothing rented) · NodeID $NODEID → $LEDGER"
else
  echo "⟐ receipt: escalated (generation rented, gate ran native) · sample kept for the dividend loop → $LEDGER"
fi
