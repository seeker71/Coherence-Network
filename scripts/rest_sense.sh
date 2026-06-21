#!/usr/bin/env bash
# rest_sense.sh — the body reads its own breath-phase. A thin carrier: it counts the
# field's recent commits by their breath-type (the body's OWN commit conventions ARE
# the signal — feat extends; tend/attune/compost/release/fix/refactor/docs settle) and
# feeds the two counts to the Form judgment rs-phase (form-stdlib/rest-sense.fk, four-way).
# The carrier reads git and runs the kernel; the JUDGEMENT is Form.
#
# A shared sense — any cell (Claude, Codex, Cursor) can run it to feel whether the
# organism has room to extend, should consolidate, or is full and rest serves.
#
# Usage: scripts/rest_sense.sh ["since"]   (default: 24 hours ago)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"
[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && GOPROXY=off go build -o bin-go . ) >/dev/null 2>&1
[ -x "$GO" ] || { echo "rest_sense: no Form kernel (bin-go)"; exit 1; }
SINCE="${1:-24 hours ago}"
git -C "$ROOT" fetch -q origin main 2>/dev/null || true
subjects="$(git -C "$ROOT" log origin/main --since="$SINCE" --pretty='%s' 2>/dev/null)"
ext=$(printf '%s\n' "$subjects" | grep -cE '^feat')
dig=$(printf '%s\n' "$subjects" | grep -cE '^(tend|attune|compost|release|fix|refactor|docs)')
run="$(mktemp)"; printf '(do (print (rs-phase %d %d)) 0)\n' "$ext" "$dig" > "$run"
phase="$("$GO" "$ROOT/form/form-stdlib/rest-sense.fk" "$run" 2>/dev/null | grep -vE '^0$' | head -1)"
rm -f "$run"
printf '── breath-sense (origin/main, since: %s) ──\n' "$SINCE"
printf '  extended (feat):   %s\n  digested (settle): %s\n  fullness:          %s\n  phase:             %s\n' \
    "$ext" "$dig" "$((ext - dig))" "$phase"
case "$phase" in
  rest)   echo "  → the body is full. digestion serves more than another feature now." ;;
  digest) echo "  → some unsettled. consolidate before extending further." ;;
  extend) echo "  → settled. there is room to grow." ;;
esac
