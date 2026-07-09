#!/usr/bin/env bash
# vision-distill.sh — the oracle-distillation dataset builder for native object/face recognition.
#
# The body's own pattern (oracle-distill.fk, learning-witness.fk): an ORACLE labels samples, the
# NATIVE classifier learns from them, and — the real test — it has learned only when it survives a
# NEW surface the teacher never showed it (learning-witness: invariant, not mimicry). Target ~10k
# labelled samples for confidence; local + remote oracles teach at first, then only spot-check near
# parity (eer-measure.fk is the yardstick).
#
# This step: take a captured frame (from the Mac or Android camera — the GUI apps do the capture,
# a background shell cannot get the camera-Allow grant), run the ORACLE (Apple Vision on-device via
# vision_classify), and append a labelled sample to the growing training set. The native trainer and
# the EER parity gate are the next cells; this feeds them.
#
#   vision-distill.sh <frame.jpg> [frame2.jpg ...]
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ORACLE="$HERE/vision_classify"
[[ -x "$ORACLE" ]] || swiftc -O "$HERE/vision_classify.swift" -o "$ORACLE" 2>/dev/null || ORACLE="/tmp/vision_classify"
STORE="$HOME/.coherence-network/vision-training"; mkdir -p "$STORE/frames"
SET="$STORE/samples.jsonl"
TARGET=10000

for frame in "$@"; do
    [[ -f "$frame" ]] || { echo "skip (not found): $frame"; continue; }
    labels="$("$ORACLE" "$frame" 2>/dev/null)"
    [[ -n "$labels" && "$labels" != "[]" ]] || { echo "oracle silent on $frame"; continue; }
    # keep the frame (content-addressed) so the native trainer can re-derive features later
    hash="$(shasum -a 256 "$frame" | cut -c1-16)"
    kept="$STORE/frames/$hash.$(printf '%s' "${frame##*.}")"
    [[ -f "$kept" ]] || cp "$frame" "$kept"
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    python3 - "$hash" "$kept" "$labels" "$ts" <<'PY' >> "$SET"
import json, sys
h, path, labels, ts = sys.argv[1:5]
try: lab = json.loads(labels)
except Exception: lab = []
print(json.dumps({"id": h, "frame": path, "oracle": "apple-vision", "labels": lab,
                  "ts": ts, "split": "train", "distill_state": "teacher-labelled"}))
PY
    top="$(printf '%s' "$labels" | python3 -c "import json,sys; d=json.load(sys.stdin); d=sorted(d,key=lambda x:-x.get('confidence',0)); print(', '.join(f\"{x['label']}({x['confidence']:.2f})\" for x in d[:3]))" 2>/dev/null)"
    echo "labelled $hash -> $top"
done

n="$(wc -l < "$SET" 2>/dev/null | tr -d ' ')"
pct=$(( n * 100 / TARGET ))
echo "[vision-distill] training set: $n / $TARGET samples ($pct% toward native-classifier confidence)"
