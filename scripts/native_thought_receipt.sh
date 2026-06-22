#!/usr/bin/env bash
# native_thought_receipt.sh — record ONE native-thought-execution routing decision, ON THE FKWU LANE.
#
# The logic is Form (form-stdlib/native-thought-receipt.fk + the proven gate sovereignty-receipt.fk),
# flattened and run by fkwu — the 4th kernel emitted from Form and compiled native from C, with NO
# Go/Rust/Python in its runtime path. This shell only stages 7 RAW newline-separated fields into the
# input_byte channel and hands them to scripts/fkwu_run.sh; the recipe parses, escapes (in Form), runs
# the honesty gate, and appends via host-io. Data crosses as data — the carrier never synthesizes Form
# source and never escapes. The one refusal (a row that fails honest?) is the Form gate's, not the shell's.
#
# Usage: native_thought_receipt.sh <body-hit|escalated> <structural|frontier> <nodeid|-> [query...]
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"
LEDGER="${NATIVE_THOUGHT_RECEIPTS:-$HOME/.coherence-network/native-thought-receipts.jsonl}"

PATHK="${1:-}"; KIND="${2:-}"; NODEID="${3:--}"; shift 3 2>/dev/null || true; QUERY="${*:-}"
case "$PATHK" in body-hit|escalated) ;; *) echo "usage: $0 <body-hit|escalated> <structural|frontier> <nodeid|-> [query]"; exit 2;; esac
mkdir -p "$(dirname "$LEDGER")"

# the only munge: newlines would break the field separator → flatten them to spaces (data, not logic)
flat(){ printf '%s' "$1" | tr '\n\r' '  '; }
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; COMMIT="$(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"

bundle="$(mktemp)"
printf '%s\n%s\n%s\n%s\n%s\n%s\n%s' \
  "$(flat "$LEDGER")" "$TS" "$COMMIT" "$PATHK" "$(flat "$KIND")" "$(flat "$NODEID")" "$(flat "$QUERY")" > "$bundle"

OUT="$(bash "$ROOT/scripts/fkwu_run.sh" "$bundle" \
        "$STD/sovereignty-receipt.fk" "$STD/native-thought-receipt.fk" "$STD/native-thought-receipt-main.fk" \
        2>/dev/null | grep -E '^(ok:|refused)' | head -1)"
rc=$?
rm -f "$bundle"

case "$OUT" in
  ok:body-hit)  echo "⟐ receipt (fkwu, native): body-hit — native lookup, nothing rented · NodeID $NODEID → $LEDGER" ;;
  ok:escalated) echo "⟐ receipt (fkwu, native): escalated — generation rented, gate ran native · sample kept for the dividend loop → $LEDGER" ;;
  refused)      echo "receipt failed honest? — the Form gate refused to write it"; exit 1 ;;
  *)            echo "the fkwu lane returned no receipt (rc=$rc) — is clang present to bootstrap the 4th kernel?"; exit 1 ;;
esac
