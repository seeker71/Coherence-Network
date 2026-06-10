#!/usr/bin/env python3
"""whisper_server.py — keep the best whisper model RESIDENT; transcribe wav paths from stdin → JSON stdout.

The oracle we learn from should be best-quality (large-v3-turbo, not tiny). But a fresh subprocess reloads
the 1.5 GB model every chunk (~5 s); held resident it loads once and then transcribes in ~0.5 s. This is a
pure host carrier — the body learns from what it says; this only keeps the speaker warm.

Protocol: one wav path per stdin line → one JSON line on stdout {t: text, l: language, n: no_speech_prob}.
Only JSON goes to stdout; model-load chatter is stderr (the parent sends it to a log).
"""
import json
import sys

import mlx_whisper

MODEL = sys.argv[1] if len(sys.argv) > 1 else "mlx-community/whisper-large-v3-turbo"
print(json.dumps({"ready": True, "model": MODEL}), flush=True)

for line in sys.stdin:
    path = line.strip()
    if not path:
        continue
    try:
        r = mlx_whisper.transcribe(path, path_or_hf_repo=MODEL, verbose=False)
        seg = r.get("segments") or [{}]
        out = {"t": r.get("text", ""), "l": r.get("language", "?"), "n": seg[0].get("no_speech_prob", 1.0)}
    except Exception as e:
        out = {"t": "", "l": "?", "n": 1.0, "err": str(e)[:100]}
    print(json.dumps(out), flush=True)
