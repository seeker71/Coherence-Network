#!/usr/bin/env python3
"""satsang-diarize.py — cluster a transcript into anonymous speakers by voice, so a human
who was in the room can label them by reading. The machine groups voices that sound alike;
the human names them from memory.

Key to far-mic quality: cluster on whole speaking TURNS (whisper segments merged across
short pauses), not tiny fragments — a 1-2s clip embeds noisily, a several-second turn embeds
steadily. Local + ungated: Resemblyzer + scipy.

  satsang-diarize.py <clean.wav> <whisper.json> <out.txt> [num_speakers] [pause_s]
"""
import sys, json
import numpy as np
import soundfile as sf
from resemblyzer import VoiceEncoder, preprocess_wav
from scipy.cluster.hierarchy import linkage, fcluster

wav_path, json_path, out_path = sys.argv[1:4]
K = int(sys.argv[4]) if len(sys.argv) > 4 else 6
PAUSE = float(sys.argv[5]) if len(sys.argv) > 5 else 1.2   # gap that ends a turn

wav, sr = sf.read(wav_path)
if wav.ndim > 1:
    wav = wav.mean(axis=1)
enc = VoiceEncoder()

segs = [s for s in json.load(open(json_path)).get("transcription", []) if s["text"].strip()]

# 1. merge consecutive segments into TURNS, breaking on a pause > PAUSE seconds.
turns = []
cur = None
for seg in segs:
    s = seg["offsets"]["from"] / 1000.0
    e = seg["offsets"]["to"] / 1000.0
    txt = seg["text"].strip()
    if cur and (s - cur["end"]) <= PAUSE:
        cur["end"] = e
        if txt != cur["lines"][-1]:      # de-loop within a turn
            cur["lines"].append(txt)
    else:
        cur = {"start": s, "end": e, "lines": [txt]}
        turns.append(cur)

# 2. embed each turn (needs >=1s of audio to be reliable).
embs = []
for t in turns:
    a = wav[int(t["start"] * sr):int(t["end"] * sr)]
    if len(a) < int(sr * 1.0):
        embs.append(None); continue
    try:
        embs.append(enc.embed_utterance(preprocess_wav(a, source_sr=sr)))
    except Exception:
        embs.append(None)

good = [i for i, v in enumerate(embs) if v is not None]
X = np.array([embs[i] for i in good])
Z = linkage(X, method="ward")
labels = fcluster(Z, t=K, criterion="maxclust")
turn_spk = {gi: int(labels[j]) for j, gi in enumerate(good)}

# short turns inherit the previous speaker
last = None
for i, t in enumerate(turns):
    spk = turn_spk.get(i, last)
    t["spk"] = spk
    if spk is not None:
        last = spk

with open(out_path, "w") as f:
    f.write("# Satsang transcript — diarized into anonymous speakers, one block per turn.\n")
    f.write("# Fill the legend, then find/replace 'Speaker N' with the name:\n#\n")
    for n in range(1, K + 1):
        f.write(f"#   Speaker {n} = \n")
    f.write("#\n# (far-mic audio: a voice can still split or merge across numbers;\n")
    f.write("#  the [mm:ss] lets you check the audio where a block looks wrong.)\n")
    for t in turns:
        label = f"Speaker {t['spk']}" if t.get("spk") else "Speaker ?"
        f.write(f"\n[{int(t['start']//60):02d}:{int(t['start']%60):02d}] {label}:\n")
        for line in t["lines"]:
            f.write(f"  {line}\n")

print(f"diarized {len(turns)} turns into {K} speakers -> {out_path}")
