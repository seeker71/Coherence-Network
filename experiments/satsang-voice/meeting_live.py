#!/usr/bin/env python3
"""meeting_live.py — the live meeting companion: listen, transcribe, classify, learn, hold the turn.

Per chunk of real audio: whisper writes the TRANSCRIPT, SoundAnalysis names the sound CATEGORY (the
3rd-party oracle), a cheap energy feature + nearest-shape (the BODY, via the kernel) learn that category
(co-learning M1), the utterance is appended to a conversation, and turn-taking.fk (the BODY) decides
whether the agent speaks — which on day one is almost never (it has learned no "speak" moment yet, and is
not named). Carrier-last: this file only marshals (mic, whisper, the swift oracle, the kernel); the
recognition, the learning, and the speak/stay decision are Form.

PRIVACY: the transcript is processed and shown LOCALLY only (for you, in this room). It is never sent
anywhere and never written into a committed artifact. Local compute IS the consent.

Carriers (Mac): ffmpeg (mic), mlx-whisper (STT), swift sound_classify (SoundAnalysis), form-kernel-rust.
Run:  COH_FORM=<worktree>/form COH_KERNEL=<...>/form-kernel-rust  python3 meeting_live.py [n_chunks]
"""
import json
import os
import struct
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FORM = os.environ.get("COH_FORM", os.path.join(REPO, "form"))
KERNEL = os.environ.get("COH_KERNEL", os.path.join(FORM, "form-kernel-rust", "target", "release", "form-kernel-rust"))
ORACLE = os.environ.get("COH_SOUND_CLASSIFY", "/tmp/sound_classify")
WHISPER_PY = os.environ.get("COH_WHISPER_PY", "/tmp/whisper-env/bin/python")
WHISPER_MODEL = os.environ.get("COH_WHISPER_MODEL", "mlx-community/whisper-tiny")
AGENT_NAME = os.environ.get("COH_AGENT_NAME", "claude").lower()
CHUNK_S = int(os.environ.get("COH_CHUNK", "6"))
TMP = "/tmp/coh-meeting"
os.makedirs(TMP, exist_ok=True)


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def record(dst):
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-i", ":0",
        "-t", str(CHUNK_S), "-ar", "16000", "-ac", "1", "-y", dst])
    return dst


COARSE = (("speech", ("speech", "voice", "sing", "narrat", "whisper", "shout", "conversation")),
          ("music", ("music", "instrument", "guitar", "piano", "bell", "chime", "drum", "tone")),
          ("animal", ("animal", "bird", "insect", "cricket", "dog", "cat", "frog", "chirp")))


def coarse(label):
    l = (label or "").lower()
    for name, keys in COARSE:
        if any(k in l for k in keys):
            return name
    return "other"


def sound_oracle(wav):
    out = sh([ORACLE, wav]).stdout.strip()
    try:
        arr = json.loads(out)
        return coarse(arr[0]["label"]) if arr else "other"
    except Exception:
        return "other"


def transcribe(wav):
    out = sh([WHISPER_PY, "-c",
              f"import mlx_whisper,sys;print(mlx_whisper.transcribe(sys.argv[1],"
              f"path_or_hf_repo='{WHISPER_MODEL}')['text'])", wav])
    return (out.stdout or "").strip()


def feature(wav):
    try:
        w = wave.open(wav, "rb"); raw = w.readframes(w.getnframes()); w.close()
        s = struct.unpack("<%dh" % (len(raw) // 2), raw[: (len(raw) // 2) * 2])
    except Exception:
        return [0] * 8
    if not s:
        return [0] * 8
    win = max(1, len(s) // 8)
    return [min(9, (sum(abs(x) for x in s[i*win:(i+1)*win] or [0]) // len(s[i*win:(i+1)*win] or [1])) // 800)
            for i in range(8)]


def kernel(recipe, expr):
    drv = os.path.join(TMP, "drv.fk")
    with open(drv, "w") as fh:
        fh.write(expr)
    out = sh([KERNEL, recipe, drv], cwd=FORM)
    line = (out.stdout or out.stderr).strip().splitlines()
    return line[-1].strip().strip('"') if line else "?"


def ns_predict(feat, exemplars):
    if not exemplars:
        return "?"
    fv = " ".join(map(str, feat))
    protos = " ".join('(list "%s" (list %s))' % (l, " ".join(map(str, f))) for l, f in exemplars)
    return kernel("form-stdlib/nearest-shape.fk", f"(do (ns-label (list {fv}) (list {protos})))")


def tt_speak(named, context, tt_exemplars, floor, pause, pause_floor):
    # the BODY decides whether to speak — turn-taking.fk composes nearest-shape.
    # run with both preluded by concatenating the two recipe files into one driver dir is overkill;
    # the kernel accepts multiple recipe files before the driver.
    fv = " ".join(map(str, context))
    protos = " ".join('(list "%s" (list %s))' % (l, " ".join(map(str, f))) for l, f in tt_exemplars)
    drv = os.path.join(TMP, "tt.fk")
    with open(drv, "w") as fh:
        fh.write(f"(do (tt-speak? {named} 0 (list {fv}) (list {protos}) {floor} {pause} {pause_floor}))")
    out = sh([KERNEL, "form-stdlib/nearest-shape.fk", "form-stdlib/turn-taking.fk", drv], cwd=FORM)
    line = (out.stdout or out.stderr).strip().splitlines()
    return (line[-1].strip() if line else "0") == "1"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    for p, n_ in ((KERNEL, "kernel"), (ORACLE, "oracle"), (WHISPER_PY, "whisper")):
        if not os.path.exists(p):
            print(f"missing {n_}: {p}"); sys.exit(1)

    sound_ex = []            # the co-learning sound classifier's exemplars
    tt_ex = []               # turn-taking's learned "speak"/"stay" moments (empty day one)
    conversation = []        # utterances: (t, category, words, named)
    s_checks = s_agree = 0
    last_t = None
    spoke = False
    print(f"meeting companion — listening, {n} chunks of {CHUNK_S}s. (transcript shown locally only)\n")
    for i in range(n):
        wav = record(os.path.join(TMP, f"c{i}.wav"))
        t = int(time.time())
        text = transcribe(wav)
        cat = sound_oracle(wav)
        feat = feature(wav)
        words = len(text.split())
        named = 1 if AGENT_NAME in text.lower() else 0

        # co-learning: the Form sound classifier predicts then learns the oracle's category
        pred = ns_predict(feat, sound_ex)
        if pred != "?":
            s_checks += 1
            if pred == cat:
                s_agree += 1
        sound_ex.append((cat, feat))

        # the conversation + the turn-taking context
        pause = 0 if last_t is None else max(0, t - last_t - CHUNK_S)
        last_t = t
        conversation.append((t, cat, words, named))
        context = [min(9, pause), named, min(9, words)]
        speak = tt_speak(named, context, tt_ex, 2, min(9, pause), 1)
        spoke = spoke or speak

        rate = round(100 * s_agree / s_checks) if s_checks else 0
        decision = "SPEAK" if speak else "listen"
        # transcript shown locally; only a short head echoed so the room sees it's live
        head = " ".join(text.split()[:8])
        print(f"[{i+1}] {cat:<7} {words:>2}w | sound-learn {rate:>3}% | turn: {decision:<6} "
              f"| “{head}{'…' if words > 8 else ''}”")

    print(f"\n{len(conversation)} utterances; the Form sound-classifier reached {rate}% agreement with "
          f"the SoundAnalysis oracle; the agent {'offered its voice' if spoke else 'stayed silent'}"
          f"(day one — it has learned no 'speak' moment and was not named). The body learns; it waits its turn.")


if __name__ == "__main__":
    main()
