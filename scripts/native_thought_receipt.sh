#!/usr/bin/env bash
# native_thought_receipt.sh — THIN DOOR to the Form recipe that records a native-thought-execution
# routing decision. The logic is Form (form-stdlib/native-thought-receipt.fk): it decides the receipt's
# honesty with the proven gate (sovereignty-receipt.fk -> 255) and appends through the kernel's host-io
# (file_append_bytes). This shell only escapes the args and hands the recipe to the kernel — "the carrier
# is a thin door, not a script." Host effects never touch bash; they come home to Form.
#
# Usage: native_thought_receipt.sh <body-hit|escalated> <structural|frontier> <nodeid|-> [query...]
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
LEDGER="${NATIVE_THOUGHT_RECEIPTS:-$HOME/.coherence-network/native-thought-receipts.jsonl}"

PATHK="${1:-}"; KIND="${2:-}"; NODEID="${3:--}"; shift 3 2>/dev/null || true; QUERY="${*:-}"
case "$PATHK" in body-hit|escalated) ;; *) echo "usage: $0 <body-hit|escalated> <structural|frontier> <nodeid|-> [query]"; exit 2;; esac
[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) >/dev/null 2>&1
[ -x "$GO" ] || { echo "form kernel unavailable — run scripts/ensure_form_cli_kernel.sh"; exit 1; }
mkdir -p "$(dirname "$LEDGER")"

# escaping is the carrier's data-munging (not logic). Two transforms, both (\\ -> \\\\, " -> \\"):
#   esc  — once, for a Form string literal (the ledger path).
#   jesc — twice, for a value that is first JSON-escaped then carried through a Form literal.
esc(){  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
jesc(){ esc "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; COMMIT="$(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"

drv="$(mktemp --suffix=.fk)"
printf '(do (print (ntr-record "%s" "%s" "%s" "%s" "%s" "%s" "%s")))\n' \
  "$(esc "$LEDGER")" "$TS" "$COMMIT" "$PATHK" "$(jesc "$KIND")" "$(jesc "$NODEID")" "$(jesc "$QUERY")" > "$drv"
OUT="$("$GO" "$STD/sovereignty-receipt.fk" "$STD/native-thought-receipt.fk" "$drv" 2>/dev/null | grep -E '^(ok:|refused)' | head -1)"
rm -f "$drv"

case "$OUT" in
  ok:body-hit)  echo "⟐ receipt: body-hit (native lookup, nothing rented) · NodeID $NODEID → $LEDGER" ;;
  ok:escalated) echo "⟐ receipt: escalated (generation rented, gate ran native) · sample kept for the dividend loop → $LEDGER" ;;
  refused)      echo "receipt failed honest? — the Form gate refused to write it"; exit 1 ;;
  *)            echo "the recipe did not return a receipt — nothing written"; exit 1 ;;
esac
