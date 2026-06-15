#!/usr/bin/env python3
"""extract_fingerprints.py — CARRIER tissue (host-IO), authored last.

This is NOT the learning body. It only turns real audio into the coarse
quantized FEATURE-VECTOR that the Form-native learner (form-stdlib/nearest-shape.fk)
eats. The recognition/learning itself lives in Form; this script is the front-end
that decodes a .flac with ffmpeg and reduces it to a small log-mel fingerprint,
quantized to the integer bins nearest-shape's per-bin Hamming similarity needs.

Per utterance it emits one JSONL row: {speaker, sex, utt, vec:[int...]}.
The vec is a normalized log-mel spectral ENVELOPE (a coarse timbre fingerprint),
quantized to Q levels over N mel bands — same speaker -> many agreeing bins,
different speaker -> fewer. That per-bin agreement count is exactly ns-sim.

Usage:
  extract_fingerprints.py --root <LibriSpeech subset dir> --speakers <SPEAKERS.TXT>
                          --out fingerprints.jsonl [--bands 13] [--levels 8]
                          [--limit N] [--lo -4.0 --hi 4.0]
"""
import argparse, json, subprocess, sys, os, glob
import numpy as np

SR = 16000
N_FFT = 512
WIN = 400      # 25 ms
HOP = 160      # 10 ms


def mel_filterbank(n_bands, sr=SR, n_fft=N_FFT, fmin=0.0, fmax=8000.0):
    def hz2mel(f): return 2595.0 * np.log10(1.0 + f / 700.0)
    def mel2hz(m): return 700.0 * (10.0 ** (m / 2595.0) - 1.0)
    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_bands + 2)
    hz = mel2hz(mels)
    bins = np.floor((n_fft + 1) * hz / sr).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)
    fb = np.zeros((n_bands, n_fft // 2 + 1), dtype=np.float64)
    for i in range(1, n_bands + 1):
        l, c, r = bins[i - 1], bins[i], bins[i + 1]
        if c == l: c = l + 1
        if r == c: r = c + 1
        for k in range(l, c):
            fb[i - 1, k] = (k - l) / max(c - l, 1)
        for k in range(c, r):
            fb[i - 1, k] = (r - k) / max(r - c, 1)
    return fb


def decode_pcm(path):
    """ffmpeg: flac -> 16k mono s16le raw -> float32 numpy in [-1,1]."""
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
         "-f", "s16le", "-"],
        capture_output=True)
    if p.returncode != 0 or not p.stdout:
        return None
    x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return x


def fingerprint(x, fb, n_bands, levels, lo, hi):
    """log-mel envelope -> normalized shape -> quantized int bins."""
    if x is None or len(x) < WIN:
        return None
    win = np.hanning(WIN).astype(np.float32)
    n_frames = 1 + (len(x) - WIN) // HOP
    if n_frames < 3:
        return None
    acc = np.zeros(n_bands, dtype=np.float64)
    for fr in range(n_frames):
        seg = x[fr * HOP: fr * HOP + WIN] * win
        spec = np.abs(np.fft.rfft(seg, N_FFT)) ** 2
        mel = fb @ spec
        acc += np.log(mel + 1e-10)
    env = acc / n_frames
    env = env - env.mean()                 # CMN-ish: a timbre SHAPE, not loudness
    q = np.round((env - lo) / (hi - lo) * (levels - 1))
    q = np.clip(q, 0, levels - 1).astype(int)
    return q.tolist()


def load_sex(speakers_txt):
    sex = {}
    if not speakers_txt or not os.path.exists(speakers_txt):
        return sex
    with open(speakers_txt) as f:
        for line in f:
            if line.startswith(";"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2 and parts[0].isdigit():
                sex[parts[0]] = parts[1]
    return sex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--speakers", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bands", type=int, default=13)
    ap.add_argument("--levels", type=int, default=8)
    ap.add_argument("--lo", type=float, default=-4.0)
    ap.add_argument("--hi", type=float, default=4.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    fb = mel_filterbank(args.bands)
    sex = load_sex(args.speakers)
    flacs = sorted(glob.glob(os.path.join(args.root, "**", "*.flac"), recursive=True))
    if args.limit:
        flacs = flacs[: args.limit]

    n_ok = 0
    with open(args.out, "w") as out:
        for i, path in enumerate(flacs):
            base = os.path.basename(path).rsplit(".", 1)[0]   # spk-chap-utt
            spk = base.split("-")[0]
            vec = fingerprint(decode_pcm(path), fb, args.bands,
                              args.levels, args.lo, args.hi)
            if vec is None:
                continue
            out.write(json.dumps({"speaker": spk, "sex": sex.get(spk, "?"),
                                  "utt": base, "vec": vec}) + "\n")
            n_ok += 1
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(flacs)} processed, {n_ok} ok", file=sys.stderr)
    print(f"wrote {n_ok} fingerprints -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
