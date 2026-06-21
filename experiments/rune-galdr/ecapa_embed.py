#!/usr/bin/env python3
"""ecapa_embed.py — the speaker-embedding ORACLE carrier (best local speaker model).

Maps a voice clip to a 192-d ECAPA-TDNN embedding (SpeechBrain spkrec-ecapa-voxceleb),
L2-normalizes it, and prints it as space-separated quantized ints (×1000) — one line per
window. This is a thin oracle wrapper, like whisper-cli (STT) or demucs (separation): it
produces features. The recognition DECISION is the Form body (form-stdlib/speaker-embed.fk:
se-nearest / se-confident? over the cosine = integer dot product of these vectors).

Runs in the torch venv (~/.coherence-network/demucs-venv). The ECAPA model auto-downloads
(~80 MB) on first use and is cached.

  ecapa_embed.py WAV                      # whole-file embedding -> one line
  ecapa_embed.py WAV START DUR HOP N      # N windows of DUR sec from START, stepping HOP
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
import torch, torchaudio
from speechbrain.inference.speaker import EncoderClassifier

SCALE = 1000
# cache the model OUTSIDE the repo (private), never in the worktree
SAVEDIR = os.path.expanduser("~/.coherence-network/ecapa-model")

_model = None
def model():
    global _model
    if _model is None:
        _model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=SAVEDIR,
            run_opts={"device": "cpu"})
    return _model

def emb(wav_t, sr):
    if sr != 16000:
        wav_t = torchaudio.functional.resample(wav_t, sr, 16000)
    with torch.no_grad():
        e = model().encode_batch(wav_t).squeeze()      # 192-d
    e = e / (e.norm() + 1e-9)                            # L2 normalize -> cosine = dot
    return " ".join(str(int(round(float(x) * SCALE))) for x in e)

def main():
    wav = sys.argv[1]
    sig, sr = torchaudio.load(wav)
    sig = sig.mean(0, keepdim=True)                      # mono
    if len(sys.argv) >= 6:
        start, dur, hop, n = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
        for i in range(n):
            t0 = int((start + i * hop) * sr); t1 = t0 + int(dur * sr)
            if t1 > sig.shape[1]: break
            print(emb(sig[:, t0:t1], sr))
    else:
        print(emb(sig, sr))

if __name__ == "__main__":
    main()
