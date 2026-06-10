#!/usr/bin/env python3
"""affect_sense.py — one-shot felt-sense carrier: a WAV in, the body's affect readings out.

The carrier MEASURES with free oracles; the BODY (affect-traits.fk, through the kernel) bands and
gates. Every oracle is optional — an absent oracle leaves its lane FORMING (shown as "·", never a
faked label), exactly the discipline of channel_live.py. What each lane needs:

  gate        — loudness from the WAV itself (pure stdlib, no deps); speechiness from any Whisper
                (mlx-whisper / faster-whisper / openai-whisper). No STT → the gate can reach 1
                (audible) but never 2 (voiced): music lanes open, speech lanes stay forming. Honest.
  cadence     — librosa (free): beat-tracker BPM + inter-onset intervals → music-cadence-band +
                pulse-steadiness. parselmouth (free, Praat): voiced-segment rate → speech-cadence-band.
  felt plane  — audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim (HF, research license):
                arousal/valence/dominance ≈0..1 → ×100 ints → felt-vec + felt-quadrant.
  sentiment   — emotion2vec+ via funasr (free): 9-class label + confidence → earned only through
                affect-trust / mood-trust / report-sentiment? — the body decides, the oracle proposes.

Fine-tuning ground (free): RAVDESS, CREMA-D (speech, acted); MTG-Jamendo 56 mood tags, DEAM
valence-arousal curves (music). The Form proof is form-stdlib/tests/affect-traits-band.fk (65535).

Run:  python3 affect_sense.py clip.wav
Deps: none required; each of `pip install librosa praat-parselmouth funasr transformers torch`
unlocks its lane.
"""
import json
import math
import os
import struct
import sys
import subprocess
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FORM = os.environ.get("COH_FORM", os.path.join(REPO, "form"))
KERNEL = os.environ.get("COH_KERNEL", os.path.join(FORM, "form-kernel-rust", "target", "release", "form-kernel-rust"))
LOUD_FLOOR = int(os.environ.get("COH_LOUD_FLOOR", "40"))
SPEECH_FLOOR = int(os.environ.get("COH_SPEECH_FLOOR", "40"))
SENT_FLOOR = int(os.environ.get("COH_SENT_FLOOR", "60"))
TMP = "/tmp/coh-affect"
os.makedirs(TMP, exist_ok=True)

FORMING = "·"


def kernel(files, expr):
    drv = os.path.join(TMP, "drv.fk")
    with open(drv, "w") as fh:
        fh.write(expr)
    out = subprocess.run([KERNEL] + files + [drv], capture_output=True, text=True, cwd=FORM)
    lines = (out.stdout or out.stderr).strip().splitlines()
    return lines[-1].strip() if lines else "?"


def loudness_db(path):
    # voiced.fk convention: mean_volume_dB + 90 (silence ~34, speech ~70). Pure stdlib.
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        raw = w.readframes(n)
        ch, width = w.getnchannels(), w.getsampwidth()
    if width != 2 or n == 0:
        return 0
    samples = struct.unpack("<%dh" % (len(raw) // 2), raw)[::ch]
    rms = math.sqrt(sum(s * s for s in samples) / len(samples)) or 1.0
    return int(round(20 * math.log10(rms / 32768.0))) + 90


def speechiness(path):
    # 100 − no_speech_prob·100, from whichever free Whisper is installed. None → forming.
    try:
        from faster_whisper import WhisperModel
        segs, info = WhisperModel("tiny", compute_type="int8").transcribe(path)
        first = next(iter(segs), None)
        return int(round((1.0 - (first.no_speech_prob if first else 1.0)) * 100)), (first.text.strip() if first else "")
    except Exception:
        pass
    try:
        import mlx_whisper
        d = mlx_whisper.transcribe(path)
        nsp = min((s.get("no_speech_prob", 1.0) for s in d.get("segments", [])), default=1.0)
        return int(round((1.0 - nsp) * 100)), (d.get("text") or "").strip()
    except Exception:
        return None, ""


def music_cadence(path):
    # librosa: BPM + inter-onset intervals scaled 0..9 (the pulse-steadiness signal). None → forming.
    try:
        import librosa
        import numpy as np
        y, sr = librosa.load(path, sr=16000, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo = float(np.asarray(tempo).reshape(-1)[0])  # numpy 2.x: 1-element array won't float() directly
        # steadiness must read ONSETS (beat_track imposes a steady grid, so its beats can't sense
        # rubato); merge onsets <120 ms apart — one sound's attack and decay both register
        onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
        kept = []
        for t in onsets:
            if not kept or float(t) - kept[-1] >= 0.12:
                kept.append(float(t))
        iv = np.diff(kept)
        if len(iv) >= 2:
            # scale by deviation from the median interval (±50% = full range), so a steady pulse
            # sits at the center and only real rubato spreads — never microscopic jitter
            med = float(np.median(iv)) or 1.0
            scaled = [max(0, min(9, int(round(4.5 + (float(x) / med - 1.0) * 9)))) for x in iv[:16]]
        else:
            scaled = [5, 5]
        return int(round(tempo)), scaled
    except Exception:
        return None, None


def speech_rate10(path):
    # parselmouth (Praat): voiced-segment rate as a syllable-rate stand-in, ×10. None → forming.
    try:
        import parselmouth
        snd = parselmouth.Sound(path)
        pitch = snd.to_pitch()
        voiced = [f for f in pitch.selected_array["frequency"] if f > 0]
        frames = len(pitch.selected_array["frequency"]) or 1
        # voiced fraction × a nominal 6 syl/s ceiling — a reading, refined when a syllable nucleus
        # oracle earns its place
        return int(round(len(voiced) / frames * 60))
    except Exception:
        return None


def felt_triple(path):
    # audeering w2v2 MSP-dim: (arousal, valence, dominance) ≈0..1 → ×100. None → forming.
    try:
        import torch
        import librosa
        from transformers import AutoModelForAudioClassification, Wav2Vec2FeatureExtractor
        name = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
        fe = Wav2Vec2FeatureExtractor.from_pretrained(name)
        model = AutoModelForAudioClassification.from_pretrained(name, trust_remote_code=True)
        y, _ = librosa.load(path, sr=16000, mono=True)
        with torch.no_grad():
            logits = model(**fe(y, sampling_rate=16000, return_tensors="pt")).logits[0]
        ar, dom, va = (float(x) for x in logits)  # model order: arousal, dominance, valence
        clamp = lambda v: max(0, min(100, int(round(v * 100))))
        return clamp(ar), clamp(va), clamp(dom)
    except Exception:
        return None


def sentiment(path):
    # emotion2vec+ via funasr: 9-class label + confidence ×100. None → forming.
    try:
        from funasr import AutoModel
        m = AutoModel(model="iic/emotion2vec_plus_base", disable_update=True)
        res = m.generate(path, granularity="utterance", extract_embedding=False)[0]
        scores = res.get("scores", [])
        labels = res.get("labels", [])
        if not scores:
            return None
        best = max(range(len(scores)), key=lambda i: scores[i])
        label = labels[best].split("/")[-1] if labels else "?"
        return label, int(round(scores[best] * 100))
    except Exception:
        return None


QUAD = {0: "settled-dim", 1: "heavy-charged", 2: "warm-still", 3: "bright-charged", 4: FORMING}
CAD = {0: "slow", 1: "measured", 2: "quick"}
MCAD = {0: "slow", 1: "mid", 2: "fast"}
BAND = {0: "low", 1: "mid", 2: "high"}
RECIPES = ["form-stdlib/voiced.fk", "form-stdlib/voice-traits.fk", "form-stdlib/affect-traits.fk"]


def main(path):
    loud = loudness_db(path)
    sp, text = speechiness(path)
    # the gate: no STT → speechiness 0, so gate honestly tops out at 1 (audible non-speech)
    gate = int(kernel(RECIPES, f"(do (gate-level {loud} {sp or 0} {LOUD_FLOOR} {SPEECH_FLOOR}))") or 0)

    print(f"gate        ▸ {['silence', 'audible', 'voiced'][gate]}  (loudness {loud}, speechiness {sp if sp is not None else FORMING})")
    if gate == 0:
        print("silence — the body learns nothing, says nothing.")
        return

    bpm, intervals = music_cadence(path)
    if bpm is not None:
        iv = " ".join(map(str, intervals))
        out = kernel(RECIPES, f"(do (list (music-cadence-band {bpm}) (pulse-steadiness (list {iv}))))")
        mc, steady = json.loads(out)
        print(f"music pulse ▸ {bpm} BPM {MCAD[mc]}, steadiness {steady}/9")
    else:
        print(f"music pulse ▸ {FORMING}  (librosa not installed)")

    r10 = speech_rate10(path) if gate >= 2 else None
    if r10 is not None:
        sc = int(kernel(RECIPES, f"(do (speech-cadence-band {r10}))"))
        print(f"speech pace ▸ {r10 / 10:.1f} syl/s {CAD[sc]}")
    elif gate >= 2:
        print(f"speech pace ▸ {FORMING}  (parselmouth not installed)")

    triple = felt_triple(path)
    if triple is not None:
        ar, va, dom = triple
        out = kernel(RECIPES, f"(do (list (felt-band {ar}) (felt-band {va}) (felt-band {dom}) (felt-quadrant {ar} {va})))")
        b_ar, b_va, b_dom, quad = json.loads(out)
        print(f"felt plane  ▸ arousal {BAND[b_ar]} · valence {BAND[b_va]} · dominance {BAND[b_dom]} → {QUAD[quad]}")
    else:
        print(f"felt plane  ▸ {FORMING}  (audeering w2v2 dim model not installed — research license)")

    sent = sentiment(path)
    if sent is not None:
        label, conf = sent
        out = kernel(RECIPES, f"(do (list (affect-trust {gate} {conf}) (mood-trust {gate} {conf}) "
                              f"(report-sentiment? {gate} {conf} {SENT_FLOOR})))")
        at, mt, rep = json.loads(out)
        shown = label if rep == 1 else FORMING
        lane = f"affect-trust {at}/9" if gate >= 2 else f"mood-trust {mt}/9"
        print(f"sentiment   ▸ {shown}  ({lane}, confidence {conf})")
    else:
        print(f"sentiment   ▸ {FORMING}  (emotion2vec+/funasr not installed)")

    if text:
        print(f"transcript  ▸ “{' '.join(text.split()[:12])}{'…' if len(text.split()) > 12 else ''}”")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[0])
        print("usage: python3 affect_sense.py clip.wav")
        sys.exit(1)
    main(sys.argv[1])
