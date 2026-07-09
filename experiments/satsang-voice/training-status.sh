#!/usr/bin/env bash
# training-status.sh — the training board both apps read. Every recognition domain reports from
# its OWN real store — no hardcoded rows. Each domain emits one honest line
#   name|samples/target|parity|state|stream-csv
# from live data: world/object (vision distill), speaker (the profile book), audio/sound (sound
# distill), person/face (face distill), dialog (transcript turns). We assemble those into the
# local JSON the mac app reads, and post one offer per domain to the mesh so the phone assembles
# the same board (the mesh caps a capability at 127 chars — one offer per domain fits; the whole
# board would not). Empty stores say so honestly; nothing is faked.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HOME/.coherence-network/satsang-venv/bin/python"
CN="$HOME/.coherence-network"
OUT="$CN/training-status.json"
API="${HATI_MESH:-https://api.coherencycoin.com/api}/hati/mesh"
FROM="hati-organ-macos-77a05bc8f6c24"
TARGET=10000

# ── world / object ─ vision distillation: samples + leave-one-out parity + recognized labels ──
VSTORE="$CN/vision-training/samples.jsonl"
w_n="$(wc -l < "$VSTORE" 2>/dev/null | tr -d ' ' || echo 0)"; w_n="${w_n:-0}"
w_parity="-"; w_stream=""
if [[ "$w_n" -ge 3 && -x "$VENV" ]]; then
    pline="$("$VENV" "$HERE/vision_train.py" 2>/dev/null | grep -oE 'PARITY[^0-9]*[0-9.]+' | grep -oE '[0-9.]+$' | head -1)"
    [[ -n "$pline" ]] && w_parity="$pline"
fi
w_stream="$(python3 -c "import json;s=[];[s.append(max(json.loads(l).get('labels',[{}]),key=lambda x:x.get('confidence',0)).get('label','')) for l in open('$VSTORE') if l.strip()];u=[];[u.append(x) for x in s if x and x not in u];print(','.join(u[:5]))" 2>/dev/null || echo "")"
w_state=$([[ "$w_n" -ge 3 ]] && echo "training" || echo "ready (no data)")
world_line="world / object|$w_n/$TARGET|$w_parity|$w_state|$w_stream"

# ── speaker ─ the real profile book (resemblyzer voiceprints, continuous auto-fold) ──
if [[ -x "$VENV" ]]; then
    speaker_line="$("$VENV" "$HERE/speaker_profiles.py" board 2>/dev/null || echo "speaker|0/$TARGET|-|ready|")"
else
    speaker_line="speaker|0/$TARGET|-|encoder venv missing|"
fi

# ── audio / sound ─ SoundAnalysis distillation ──
ASTORE="$CN/audio-training/samples.jsonl"
audio_line="$(python3 -c "
import json,os
p='$ASTORE'; T=$TARGET
n=sum(1 for _ in open(p)) if os.path.exists(p) else 0
labs=[]
if os.path.exists(p):
    for l in open(p):
        for x in json.loads(l).get('labels',[])[:2]:
            lab=x.get('label')
            if lab and lab not in labs: labs.append(lab)
state='training' if n>=3 else ('ready — listening' if os.path.exists(os.path.dirname(p)) else 'ready')
print(f\"audio / sound|{n}/{T}|-|{state}|{','.join(labs[:6])}\")
" 2>/dev/null || echo "audio / sound|0/$TARGET|-|ready|")"

# ── person / face ─ the real face book (Vision detect→crop→featureprint, auto-match/fold) ──
if [[ -x "$VENV" ]]; then
    face_line="$("$VENV" "$HERE/face_profiles.py" board 2>/dev/null || echo "person / face|0/$TARGET|-|ready — awaiting camera frames|")"
else
    face_line="person / face|0/$TARGET|-|encoder venv missing|"
fi

# ── dialog ─ speaker turns from the room transcripts ──
dialog_line="$(python3 "$HERE/dialog-distill.py" board 2>/dev/null || echo "dialog|0/$TARGET|-|pending|")"

# ── assemble the local JSON the mac app reads ──
python3 - "$OUT" "$world_line" "$speaker_line" "$audio_line" "$face_line" "$dialog_line" <<'PY'
import json, sys
out = sys.argv[1]; lines = sys.argv[2:]
def parse(line):
    p = line.split("|")
    n, t = (p[1].split("/") + ["0", "10000"])[:2]
    par = p[2].strip()
    stream = [s for s in p[4].split(",") if s] if len(p) > 4 else []
    return {"domain": p[0], "samples": int(n or 0), "target": int(t or 10000),
            "parity": (float(par) if par not in ("-", "") else None),
            "state": p[3], "stream": stream}
json.dump({"domains": [parse(l) for l in lines], "ts": "live"}, open(out, "w"), indent=2)
PY

# ── post ONE offer per domain to the mesh (capability capped at 127 chars) ──
post_domain() { # slug  capability
    local slug="$1" cap="${2:0:120}" pf; pf="$(mktemp)"
    python3 -c "import json,sys;json.dump({'from_organ_id':sys.argv[1],'to_organ_id':'hati-suci','protocol':'hati-mesh','interface':'learning/board/'+sys.argv[2],'capability':sys.argv[3],'codec':'json','data_type':'event','direction':'presence','status':'offered'}, open(sys.argv[4],'w'))" "$FROM" "$slug" "$cap" "$pf"
    curl -s -m 8 -o /dev/null -w "%{http_code} " -X POST "$API/channels/offer" -H "Content-Type: application/json" --data @"$pf"
    rm -f "$pf"
}
echo -n "[training-status] mesh: "
post_domain "world-object" "$world_line"
post_domain "speaker"      "$speaker_line"
post_domain "audio-sound"  "$audio_line"
post_domain "person-face"  "$face_line"
post_domain "dialog"       "$dialog_line"
echo ""
echo "[training-status] wrote $OUT (all domains from live stores)"
