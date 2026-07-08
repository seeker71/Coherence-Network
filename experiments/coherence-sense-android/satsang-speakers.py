#!/usr/bin/env python3
"""satsang-speakers.py — label a satsang transcript by speaker, using each person's
intro as their enrollment sample ("train speaker detection from the intros").

Local + ungated: Resemblyzer's bundled voice encoder — no Hugging Face, no gated models.
Far-mic audio degrades speaker embeddings, so this is best-effort: it reports a similarity
score per segment and marks low-confidence ones "?", never guessing past the evidence.

  satsang-speakers.py <clean.wav> <whisper.json> <enroll.json> <out.txt>

enroll.json maps a name to the [start_s, end_s] of that person's intro in the audio:
  { "Maya": [12.0, 21.5], "Ravi": [24.0, 33.0], ... }
"""
import sys, json
import numpy as np
import soundfile as sf
from resemblyzer import VoiceEncoder, preprocess_wav

wav_path, json_path, enroll_path, out_path = sys.argv[1:5]
THRESH = float(sys.argv[5]) if len(sys.argv) > 5 else 0.62

wav, sr = sf.read(wav_path)
if wav.ndim > 1:
    wav = wav.mean(axis=1)
encoder = VoiceEncoder()

def embed(start_s, end_s):
    a = wav[int(start_s * sr):int(end_s * sr)]
    if len(a) < int(sr * 0.6):          # < 0.6s is too little voice to embed
        return None
    try:
        return encoder.embed_utterance(preprocess_wav(a, source_sr=sr))
    except Exception:
        return None

# enroll one voice profile per named person, from their intro slice
enroll = json.load(open(enroll_path))
names, mats = [], []
for name, (s, e) in enroll.items():
    v = embed(float(s), float(e))
    if v is not None:
        names.append(name); mats.append(v)
    else:
        print(f"  ! enrollment too short for {name} ({s}-{e}s)", file=sys.stderr)
mats = np.array(mats) if mats else np.zeros((0, 256))

segs = json.load(open(json_path)).get("transcription", [])
labeled, counts = [], {}
for seg in segs:
    s = seg["offsets"]["from"] / 1000.0
    e = seg["offsets"]["to"] / 1000.0
    text = seg["text"].strip()
    if not text:
        continue
    v = embed(s, e)
    if v is None or len(names) == 0:
        spk, score = "?", 0.0
    else:
        sims = mats @ v
        i = int(np.argmax(sims))
        score = float(sims[i])
        spk = names[i] if score >= THRESH else "?"
    counts[spk] = counts.get(spk, 0) + 1
    labeled.append((s, spk, score, text))

with open(out_path, "w") as f:
    f.write(f"# Satsang transcript — speaker-labeled ({len(names)} enrolled: {', '.join(names)})\n")
    f.write(f"# '?' = below confidence {THRESH} (far-mic audio; not guessed)\n\n")
    for s, spk, score, text in labeled:
        f.write(f"[{int(s//60):02d}:{int(s%60):02d}] {spk:>10} ({score:.2f}): {text}\n")

print(f"labeled {len(labeled)} segments; per-speaker: {counts}")
