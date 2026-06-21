#!/usr/bin/env bash
# form_cli_gold.sh — record a human's direct freq-reading into the local GOLD catalog.
#
# Carrier-last: the SHAPE is the body (form/form-stdlib/training-catalog.fk
# tc-gold-named, four-way proven). This thin door only PERSISTS your verbatim reading
# so it stops evaporating at session end. The gold lane is the strongest label the
# freq-check model learns from — a person catches the nuanced fear a frontier model
# slips past — and the NAMED boundary (WHERE the fear sat / what made it clear) is the
# richest signal, learned in meaning-space, and the seam the transmute lane acts on.
#
#   form-cli gold <clear|fear> "<where the fear sat / what made it clear>" ["<response ref>"]
#
# Local only (~/.coherence-network/freq-gold/gold.jsonl); your readings stay yours.
set -euo pipefail

v_in="${1:-}"; boundary="${2:-}"; ref="${3:-}"
case "$v_in" in
  clear|CLEAR|1)      v=1 ;;
  fear|FEAR|caught|0) v=0 ;;
  *) echo "usage: form-cli gold <clear|fear> \"<where the fear sat / what made it clear>\" [response-ref]" >&2; exit 2 ;;
esac

dir="${FREQ_GOLD_DIR:-$HOME/.coherence-network/freq-gold}"; mkdir -p "$dir"
out="$dir/gold.jsonl"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# One gold reading per line; lane matches tc-gold-named's "gold:human-freq".
# python3 is the byte-persist carrier (json escaping); the recipe is the canonical shape.
python3 - "$out" "$ts" "$v" "$boundary" "$ref" <<'PY'
import json, sys
out, ts, v, boundary, ref = sys.argv[1:6]
rec = {"ts": ts, "lane": "gold:human-freq", "verdict": int(v),
       "boundary": boundary, "named": 1 if boundary.strip() else 0, "response_ref": ref}
with open(out, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
n = sum(1 for _ in open(out, encoding="utf-8"))
kind = "clear" if int(v) else "fear-caught"
named = "named" if rec["named"] else "no boundary named"
print(f"✓ gold reading #{n} recorded — {kind} ({named}): {boundary[:72]}")
PY
