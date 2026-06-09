#!/usr/bin/env python3
"""co_learning_live.py — co-learning M1, live: a Form-native sound classifier learns from the
SoundAnalysis ORACLE on real audio, and its agreement with the oracle climbs as it learns.

The BODY is Form: per chunk, nearest-shape (the body's own classifier, run by the kernel) predicts the
sound category from a cheap energy feature, then LEARNS the oracle's label (intern one exemplar —
learning-arc's smallest act). The CARRIER (this file) only marshals: record/generate a WAV, run the
3rd-party oracle (SoundAnalysis via sound_classify), read a coarse energy feature, and read the kernel's
label out. The agreement (Form prediction vs oracle) climbing IS the Form-native arm reaching the
3rd-party classifier — the point at which the expensive oracle can retire (champion-challenger).

Carriers (Mac): ffmpeg (avfoundation mic), swift sound_classify (SoundAnalysis), form-kernel-rust.
For an autonomous demo it cycles real mic chunks + generated audio (say / system sounds) so the
classifier learns several categories; in a real meeting every chunk is the live mic.
"""
import os
import struct
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
# The recipes + a built kernel must be on the checkout you run from. COH_FORM / COH_KERNEL override
# (e.g. point at a worktree whose branch carries the recipes + a fresh `cargo build --release`).
FORM = os.environ.get("COH_FORM", os.path.join(REPO, "form"))
KERNEL = os.environ.get("COH_KERNEL", os.path.join(FORM, "form-kernel-rust", "target", "release", "form-kernel-rust"))
NS = "form-stdlib/nearest-shape.fk"
ORACLE = os.environ.get("COH_SOUND_CLASSIFY", "/tmp/sound_classify")
TMP = "/tmp/coh-colearn"
os.makedirs(TMP, exist_ok=True)


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def to_wav(src, dst):
    """Normalize any audio to 16kHz mono 16-bit WAV (so wave + the oracle both read it)."""
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-ar", "16000", "-ac", "1", dst])
    return dst


def record_mic(dst, seconds=4):
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-i", ":0",
        "-t", str(seconds), "-ar", "16000", "-ac", "1", "-y", dst])
    return dst


def gen_speech(text, dst):
    # ≥4s of speech (SoundAnalysis needs a real window; sub-second clips return []).
    aiff = dst + ".aiff"
    sh(["say", "-r", "140", "-o", aiff, text])
    return to_wav(aiff, dst)


def gen_tone(freq, dst):
    # a 5s sine — SoundAnalysis hears a sustained tone as "music".
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration=5", "-ar", "16000", "-ac", "1", dst])
    return dst


COARSE = (
    ("speech", ("speech", "voice", "sing", "narrat", "whisper", "shout")),
    ("music", ("music", "instrument", "guitar", "piano", "bell", "chime", "drum", "synth", "tone")),
    ("animal", ("animal", "bird", "insect", "cricket", "dog", "cat", "frog", "chirp", "meow", "bark")),
)


def coarse(label):
    l = (label or "").lower()
    for name, keys in COARSE:
        if any(k in l for k in keys):
            return name
    return "other"


def oracle(wav):
    """The 3rd-party SoundAnalysis classifier — the ground-truth label (coarse category)."""
    out = sh([ORACLE, wav]).stdout.strip()
    try:
        import json
        arr = json.loads(out)
        return coarse(arr[0]["label"]) if arr else "other"
    except Exception:
        return "other"


def feature(wav):
    """A cheap Form-feedable feature: the energy envelope over 8 windows, quantized 0..9. Cheaper than
    the oracle (that is the whole point — the Form arm learns to replace the expensive classifier)."""
    try:
        w = wave.open(wav, "rb")
        n, raw = w.getnframes(), w.readframes(w.getnframes())
        w.close()
        s = struct.unpack("<%dh" % (len(raw) // 2), raw[: (len(raw) // 2) * 2])
    except Exception:
        return [0] * 8
    if not s:
        return [0] * 8
    W = 8
    win = max(1, len(s) // W)
    feat = []
    for i in range(W):
        seg = s[i * win:(i + 1) * win] or [0]
        energy = sum(abs(x) for x in seg) // len(seg)
        feat.append(min(9, energy // 800))
    return feat


def ns_predict(feat, exemplars):
    """The body recognizes — nearest-shape over the learned exemplars, run by the kernel. Cold = '?'."""
    if not exemplars:
        return "?"
    fv = " ".join(str(x) for x in feat)
    protos = " ".join(
        '(list "%s" (list %s))' % (lbl, " ".join(str(x) for x in f)) for lbl, f in exemplars
    )
    drv = os.path.join(TMP, "drv.fk")
    with open(drv, "w") as fh:
        fh.write('(do (ns-label (list %s) (list %s)))' % (fv, protos))
    out = sh([KERNEL, NS, drv], cwd=FORM)
    line = (out.stdout or out.stderr).strip().splitlines()
    return line[-1].strip().strip('"') if line else "?"


def main():
    if not os.path.exists(KERNEL):
        print("kernel not built:", KERNEL); sys.exit(1)
    if not os.path.exists(ORACLE):
        print("oracle not built (swiftc sound_classify.swift -o /tmp/sound_classify):", ORACLE); sys.exit(1)

    # the audio stream: generated categories (for a clear autonomous learning curve) + real mic chunks.
    # In a real meeting every event is the live mic; here we vary the audio so the classifier learns
    # several categories rather than one ambient.
    def speech(i):   return gen_speech(
        "the circle is listening together, many bodies one field, learning when it is our turn to speak",
        os.path.join(TMP, f"sp{i}.wav"))
    def music(i):    return gen_tone(440 + (i % 3) * 110, os.path.join(TMP, f"mu{i}.wav"))
    def micchunk(i): return record_mic(os.path.join(TMP, f"mic{i}.wav"), 4)

    sources = [("speech", speech), ("music", music), ("mic", micchunk)]
    rounds = 4

    exemplars = []           # the Form classifier's learned (label, feature) exemplars
    checks = agree = 0
    print(f"{'#':>2}  {'oracle':<8} {'form-pred':<10} {'feature':<22} agree%")
    print("-" * 60)
    step = 0
    for r in range(rounds):
        for tag, src in sources:
            step += 1
            wav = src(step)
            if not wav or not os.path.exists(wav):
                continue
            o = oracle(wav)
            feat = feature(wav)
            pred = ns_predict(feat, exemplars)
            mark = ""
            if pred != "?":
                checks += 1
                if pred == o:
                    agree += 1
                    mark = "✓"
                else:
                    mark = "·"
            exemplars.append((o, feat))
            rate = round(100 * agree / checks) if checks else 0
            print(f"{step:>2}  {o:<8} {pred:<10} {str(feat):<22} {rate:>3}% {mark}")

    print("-" * 60)
    print(f"the Form-native classifier learned {len(exemplars)} exemplars; agreement with the "
          f"SoundAnalysis oracle reached {round(100*agree/checks) if checks else 0}% "
          f"({agree}/{checks}) — the native arm reaching the 3rd-party, live.")


if __name__ == "__main__":
    main()
